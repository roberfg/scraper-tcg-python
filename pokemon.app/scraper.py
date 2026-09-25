import argparse
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup
import yaml


BASIC_ENERGIES = {
    "Fighting Energy", "Water Energy", "Fire Energy", "Grass Energy",
    "Lightning Energy", "Psychic Energy", "Darkness Energy",
    "Metal Energy", "Fairy Energy", "Colorless Energy",
}

SUBTYPE_TO_BUCKET = {
    "Supporter": "supporters",
    "Item": "items",
    "Tool": "tools",
    "Stadium": "stadiums",
}

SECTIONS = ("Pokemon", "Trainer", "Energy")
OUTPUT_CATEGORIES = ("pokemon", "items", "supporters", "tools", "stadiums", "energies")

HEADERS = {
    "User-Agent": "pokemon-app/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def normalize_card_name(name):
    return re.sub(r"\s+\([A-Z0-9]+-\d+\)$", "", name.strip())


def parse_card_text(text):
    match = re.match(r"^(\d+)\s+(.+)$", text.strip())
    if not match:
        return None
    return int(match.group(1)), normalize_card_name(match.group(2))


def parse_card_href(href):
    match = re.search(r"/cards/([A-Za-z0-9]+)/([\d]+)", href or "")
    if not match:
        return None
    return match.group(1).upper(), match.group(2)


def parse_card_type_text(raw):
    match = re.match(r"^\s*(\w+)\s*(?:-\s*(\w+))?\s*$", raw)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def detect_section(heading_text):
    if heading_text.startswith("Pok"):
        return "Pokemon"
    if heading_text.startswith("Trainer"):
        return "Trainer"
    if heading_text.startswith("Energy"):
        return "Energy"
    return None


def load_formats(path="decks/decks.yaml"):
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    formats = data.get("decks") if isinstance(data, dict) else None
    if not isinstance(formats, dict):
        raise ValueError(f"{path} debe contener un objeto 'decks'.")

    result = []
    for format_name, urls in formats.items():
        if not isinstance(format_name, str) or not isinstance(urls, list):
            raise ValueError("Cada formato debe contener una lista de URLs.")
        normalized_urls = []
        for url in urls:
            if not isinstance(url, str) or not url.strip():
                raise ValueError(f"El formato '{format_name}' contiene una URL inválida.")
            normalized_urls.append(url.strip())
        result.append((format_name, normalized_urls))
    return result


def load_cards_db(path="cards_db.json"):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def write_cards_db(cards_db, path="cards_db.json"):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cards_db, file, indent=2, ensure_ascii=False)
        file.write("\n")


def load_deck_cache(path="decks_cache.json"):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def write_deck_cache(cache, path="decks_cache.json"):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)
        file.write("\n")


def parse_deck_response(content):
    deck_cards = {section: [] for section in SECTIONS}
    soup = BeautifulSoup(content, "html.parser")
    for column in soup.find_all("div", class_="column"):
        heading = column.find("div", class_="heading")
        if not heading:
            continue
        section = detect_section(heading.get_text(strip=True))
        if not section:
            continue
        for paragraph in column.find_all("p"):
            link = paragraph.find("a")
            if not link:
                continue
            parsed = parse_card_text(link.get_text())
            href_info = parse_card_href(link.get("href", ""))
            if not parsed or not href_info:
                continue
            quantity, name = parsed
            set_code, number = href_info
            if section == "Energy" and name in BASIC_ENERGIES:
                continue
            deck_cards[section].append([name, set_code, number, quantity])
    return deck_cards


def normalize_cached_deck(deck_cards):
    normalized = {section: [] for section in SECTIONS}
    for section in SECTIONS:
        for entry in deck_cards.get(section, []):
            if not isinstance(entry, list) or len(entry) != 4:
                continue
            name, set_code, number, quantity = entry
            if not isinstance(name, str) or not isinstance(quantity, int):
                continue
            normalized[section].append([
                normalize_card_name(name),
                set_code,
                number,
                quantity,
            ])
    return normalized


def scrape_deck(url, cache, refresh=False):
    if not refresh and isinstance(cache.get(url), dict):
        print(f"-> cache: {url}")
        return normalize_cached_deck(cache[url])

    print(f"-> {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as error:
        print(f"  ! Error de red: {error}")
        return {section: [] for section in SECTIONS}
    if response.status_code != 200:
        print(f"  ! HTTP {response.status_code}")
        return {section: [] for section in SECTIONS}

    deck_cards = parse_deck_response(response.content)
    cache[url] = deck_cards
    write_deck_cache(cache)
    return deck_cards


def aggregate_cards(deck_cards, glc=False):
    aggregated = {section: [] for section in SECTIONS}
    indexes = {section: {} for section in SECTIONS}
    for cards in deck_cards:
        for section in SECTIONS:
            for name, set_code, number, quantity in cards.get(section, []):
                key = (name, set_code, number)
                if key not in indexes[section]:
                    indexes[section][key] = len(aggregated[section])
                    aggregated[section].append([
                        name,
                        set_code,
                        number,
                        1 if glc else quantity,
                    ])
                    continue
                index = indexes[section][key]
                if not glc:
                    aggregated[section][index][3] = max(
                        aggregated[section][index][3], quantity
                    )
    return aggregated


def fetch_card_subtype(name, set_code, number, cards_db):
    cache_key = f"{name}|{set_code}|{number}"
    cached_info = cards_db.get(cache_key)
    if isinstance(cached_info, dict):
        return cached_info, True

    url = f"https://limitlesstcg.com/cards/{set_code}/{number}"
    backoffs = [2, 4, 8, 16, 30, 30]
    for attempt, wait in enumerate(backoffs, start=1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as error:
            print(f"  ! Error de red con '{name}': {error}")
            return None, False
        if response.status_code == 429:
            print(
                f"  ! Rate limit (429) en '{name}'; esperando {wait}s "
                f"(intento {attempt}/{len(backoffs)})..."
            )
            time.sleep(wait)
            continue
        if response.status_code != 200:
            return None, False
        break
    else:
        return None, False

    soup = BeautifulSoup(response.text, "html.parser")
    type_paragraph = soup.select_one("p.card-text-type")
    if not type_paragraph:
        return None, False
    supertype, subtype = parse_card_type_text(type_paragraph.get_text(" ", strip=True))
    info = {"supertype": supertype, "subtype": subtype}
    cards_db[cache_key] = info
    return info, False


def clear_exports(export_dir):
    os.makedirs(export_dir, exist_ok=True)
    for filename in os.listdir(export_dir):
        path = os.path.join(export_dir, filename)
        if os.path.isfile(path) and filename.lower().endswith(".txt"):
            os.unlink(path)


def write_named(path, names):
    with open(path, "w", encoding="utf-8") as file:
        for name in names:
            file.write(f"{name}\n")


def write_cards(path, cards, include_printing=False):
    with open(path, "w", encoding="utf-8") as file:
        for name, set_code, number, quantity in cards:
            printing = f" ({set_code}-{number})" if include_printing and set_code and number else ""
            file.write(f"{quantity} {name}{printing}\n")


def write_quantities(path, cards):
    with open(path, "w", encoding="utf-8") as file:
        for name, quantity in cards:
            file.write(f"{quantity} {name}\n")


def process_format(format_name, deck_cards, cards_db, export_dir):
    glc = format_name.lower() == "glc"
    aggregated = aggregate_cards(deck_cards, glc=glc)
    trainer_buckets = {bucket: [] for bucket in SUBTYPE_TO_BUCKET.values()}
    trainer_indexes = {bucket: {} for bucket in trainer_buckets}
    trainer_unknown = []
    unknown_seen = set()

    for name, set_code, number, quantity in aggregated["Trainer"]:
        info, was_cached = fetch_card_subtype(name, set_code, number, cards_db)
        if not was_cached:
            time.sleep(0.12)
        bucket = SUBTYPE_TO_BUCKET.get(info.get("subtype")) if info else None
        if not info or info.get("supertype") != "Trainer" or bucket not in trainer_buckets:
            if name not in unknown_seen:
                unknown_seen.add(name)
                trainer_unknown.append(name)
            continue
        if name not in trainer_indexes[bucket]:
            trainer_indexes[bucket][name] = len(trainer_buckets[bucket])
            trainer_buckets[bucket].append([name, quantity])
        elif not glc:
            index = trainer_indexes[bucket][name]
            trainer_buckets[bucket][index][1] = max(
                trainer_buckets[bucket][index][1], quantity
            )

    prefix = f"collection_{format_name}"
    write_cards(
        os.path.join(export_dir, f"{prefix}_pokemon.txt"),
        aggregated["Pokemon"],
        include_printing=True,
    )
    for bucket, cards in trainer_buckets.items():
        write_quantities(os.path.join(export_dir, f"{prefix}_{bucket}.txt"), cards)
    write_quantities(
        os.path.join(export_dir, f"{prefix}_energies.txt"),
        [(name, quantity) for name, _set, _number, quantity in aggregated["Energy"]],
    )
    write_named(os.path.join(export_dir, f"unknown_{format_name}.txt"), trainer_unknown)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Vuelve a descargar todos los mazos y actualiza la cache.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    formats = load_formats()
    cache = load_deck_cache()
    all_decks = {}
    for format_name, urls in formats:
        all_decks[format_name] = [
            scrape_deck(url, cache, refresh=args.refresh) for url in urls
        ]

    cards_db = load_cards_db()
    export_dir = "export"
    clear_exports(export_dir)
    for format_name, _urls in formats:
        process_format(format_name, all_decks[format_name], cards_db, export_dir)
    write_cards_db(cards_db)
    print(f"Formatos procesados: {len(formats)}")


if __name__ == "__main__":
    main()
