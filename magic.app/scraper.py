import argparse
import json
import os
import re
import time
import unicodedata
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
import yaml


BASIC_LANDS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest",
    "Snow-Covered Plains", "Snow-Covered Island",
    "Snow-Covered Swamp", "Snow-Covered Mountain",
    "Snow-Covered Forest", "Wastes",
}

CATEGORIES = (
    "creatures",
    "lands",
    "planeswalkers",
    "spells",
    "artifacts",
    "enchantments",
)

SCRYFALL_HEADERS = {
    "User-Agent": "magic-app/1.0",
    "Accept": "*/*",
}

MTGDECKS_HEADERS = {
    "User-Agent": "curl/8.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_card_line(line):
    line = re.sub(r"^SB:\s*", "", line, flags=re.IGNORECASE).strip()
    match = re.match(r"^(\d+)\s*x?\s*(.+)$", line)
    if not match:
        return None
    return int(match.group(1)), match.group(2).strip().rstrip(",")


def classify_type(type_line):
    type_line = type_line or ""
    if "Creature" in type_line:
        return "creatures"
    if "Land" in type_line:
        return "lands"
    if "Planeswalker" in type_line:
        return "planeswalkers"
    if "Instant" in type_line or "Sorcery" in type_line:
        return "spells"
    if "Artifact" in type_line:
        return "artifacts"
    if "Enchantment" in type_line:
        return "enchantments"
    return None


def fetch_card_info(name, cards_db):
    cached_info = cards_db.get(name)
    if (
        isinstance(cached_info, dict)
        and isinstance(cached_info.get("is_pauper"), bool)
        and (
            cached_info.get("type_category") in CATEGORIES
            or cached_info.get("type_category") is None
        )
    ):
        print(f"    [cache] {name}: {cached_info['is_pauper']} / {cached_info['type_category']}")
        return cached_info, True

    url = "https://api.scryfall.com/cards/named?exact=" + requests.utils.quote(name)
    print(f"    [Scryfall] Consultando '{name}'...")
    backoffs = [2, 4, 8, 16, 30, 30]
    for attempt, wait in enumerate(backoffs, start=1):
        try:
            response = requests.get(url, headers=SCRYFALL_HEADERS, timeout=15)
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
            print(f"    [Scryfall] HTTP {response.status_code} para '{name}'")
            return None, False
        break
    else:
        return None, False

    data = response.json()
    if data.get("object") == "error":
        print(f"    [Scryfall] No se encontró '{name}'")
        return None, False

    if data.get("card_faces"):
        type_lines = [face.get("type_line", "") for face in data["card_faces"]]
        type_line = " // ".join(line for line in type_lines if line) or data.get("type_line", "")
    else:
        type_line = data.get("type_line", "")

    info = {
        "is_pauper": data.get("legalities", {}).get("pauper") == "legal",
        "type_category": classify_type(type_line),
    }
    cards_db[name] = info
    print(f"    [Scryfall] '{name}': pauper={info['is_pauper']}, categoría={info['type_category']}")
    return info, False


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


def load_formats(path="decks/decks.yaml"):
    print(f"[Magic] Cargando configuración de formatos: {path}")
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
    print(
        "[Magic] Formatos cargados: "
        + ", ".join(f"{name} ({len(urls)} URLs)" for name, urls in result)
    )
    return result


def load_deck_cache(path="decks_cache.json"):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                print(f"[Magic] Caché de decks cargada: {len(data)} URLs")
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    print(f"[Magic] No se encontró una caché válida de decks: {path}")
    return {}


def write_deck_cache(cache, path="decks_cache.json"):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)
        file.write("\n")


def parse_deck_response(content):
    soup = BeautifulSoup(content, "html.parser")
    deck_area = soup.select_one("#arena_deck")
    if not deck_area:
        print("  ! No se encontró la lista #arena_deck")
        return []
    cards = []
    for line in deck_area.get_text().splitlines():
        parsed = parse_card_line(line)
        if parsed:
            cards.append(parsed)
    normalized_cards = normalize_deck_cards(cards)
    print(f"  [Magic] Cartas parseadas: {len(normalized_cards)} únicas")
    return normalized_cards


def normalize_cached_deck(deck_cards):
    cards = []
    if not isinstance(deck_cards, list):
        return cards
    for entry in deck_cards:
        if not isinstance(entry, list) or len(entry) != 2:
            continue
        quantity, name = entry
        if isinstance(quantity, int) and isinstance(name, str) and name.strip():
            cards.append([quantity, name.strip()])
    return cards


def scrape_deck(url, cache, refresh=False):
    if not refresh and isinstance(cache.get(url), list):
        print(f"[Magic] Deck desde caché: {url}")
        return normalize_cached_deck(cache[url])

    print(f"[Magic] Descargando deck: {url}")
    try:
        response = requests.get(url, headers=MTGDECKS_HEADERS, timeout=15)
    except requests.RequestException as error:
        print(f"  ! Error de red: {error}")
        return []
    if response.status_code != 200:
        print(f"  ! HTTP {response.status_code}")
        return []

    deck_cards = parse_deck_response(response.content)
    if not deck_cards:
        return []
    cache[url] = deck_cards
    write_deck_cache(cache)
    print(f"  [Magic] Deck guardado en caché: {url}")
    return deck_cards


def deck_name_from_url(url):
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"-decklist-by-[^-]+(?:-[^-]+)*-\d+$", "", slug)
    slug = re.sub(r"-decklist.*$", "", slug)
    return unquote(slug).replace("-", " ").strip() or "unnamed"


def normalize_deck_cards(deck_cards):
    cards = {}
    order = []
    for quantity, name in deck_cards:
        if name in BASIC_LANDS:
            continue
        if name not in cards:
            order.append(name)
            cards[name] = quantity
        else:
            cards[name] = max(cards[name], quantity)
    return [[cards[name], name] for name in order]


def read_deck_file(path):
    cards = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            parsed = parse_card_line(line)
            if parsed:
                cards.append(parsed)
    normalized_cards = normalize_deck_cards(cards)
    print(f"[Magic] Leído {path}: {len(normalized_cards)} cartas únicas")
    return normalized_cards


def normalize_filename_part(value):
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    return normalized.lower() or "unnamed"


def deck_filename(deck):
    return "deck_{}_{}.txt".format(
        normalize_filename_part(deck["format"]),
        normalize_filename_part(deck["name"]),
    )


def clear_exports(exports_dir):
    os.makedirs(exports_dir, exist_ok=True)
    removed = 0
    for filename in os.listdir(exports_dir):
        path = os.path.join(exports_dir, filename)
        if os.path.isfile(path) and filename.lower().endswith(".txt"):
            os.unlink(path)
            removed += 1
    print(f"[Magic] Limpieza de {exports_dir}: {removed} archivos eliminados")


def write_card_file(path, cards):
    with open(path, "w", encoding="utf-8") as file:
        for quantity, name, reference in cards:
            suffix = f" ({reference})" if reference else ""
            file.write(f"{quantity} {name}{suffix}\n")
    print(f"[Magic] Generado {path}: {len(cards)} registros")


def process_decks(decks, cards_db, exports_dir="exports"):
    print(f"[Magic] Iniciando procesamiento de {len(decks)} mazos")
    deck_cards = []
    for deck in decks:
        print(f"[Magic] Preparando {deck['format']}/{deck['name']}")
        cards = deck.get("cards")
        if cards is None:
            cards = read_deck_file(deck["path"])
        deck_cards.append((deck, cards))

    clear_exports(exports_dir)
    pauper_cards = {category: [] for category in CATEGORIES}
    pauper_indexes = {category: {} for category in CATEGORIES}
    non_pauper_cards = {category: [] for category in CATEGORIES}
    non_pauper_indexes = {category: {} for category in CATEGORIES}
    unknown_cards = []
    unknown_seen = set()
    pauper_nonlegal_cards = []
    counters = {"pauper": 0, "nonlegal_pauper": 0, "unknown": 0}

    for deck, cards in deck_cards:
        is_pauper_deck = deck["format"].lower() == "pauper"
        print(
            f"[Magic] Procesando {deck['format']}/{deck['name']} "
            f"({len(cards)} cartas, pauper={is_pauper_deck})"
        )
        for quantity, name in cards:
            print(f"  [Magic] Carta: {quantity} {name}")
            info, was_cached = fetch_card_info(name, cards_db)
            if not was_cached:
                time.sleep(0.12)

            if info is None or info.get("type_category") not in CATEGORIES:
                print(f"    [Magic] Destino: unknown ({name})")
                if name not in unknown_seen:
                    unknown_seen.add(name)
                    unknown_cards.append(name)
                counters["unknown"] += 1
                continue

            if info["is_pauper"]:
                category = info["type_category"]
                print(f"    [Magic] Destino: collection_pauper_{category}.txt")
                index = pauper_indexes[category].get(name)
                if index is None:
                    pauper_indexes[category][name] = len(pauper_cards[category])
                    pauper_cards[category].append([quantity, name, None])
                else:
                    pauper_cards[category][index][0] = max(
                        pauper_cards[category][index][0], quantity
                    )
                counters["pauper"] += 1
                continue

            category = info["type_category"]
            index = non_pauper_indexes[category].get(name)
            if index is None:
                non_pauper_indexes[category][name] = len(non_pauper_cards[category])
                non_pauper_cards[category].append([quantity, name, None])
            else:
                non_pauper_cards[category][index][0] = max(
                    non_pauper_cards[category][index][0], quantity
                )

            if is_pauper_deck:
                print(f"    [Magic] Destino: collection_non_pauper_{category}.txt")
                pauper_nonlegal_cards.append([
                    quantity,
                    name,
                    deck_filename(deck).removesuffix(".txt"),
                ])
                counters["nonlegal_pauper"] += 1
                continue

        print(f"[Magic] No se genera lista individual para {deck['name']}")

    write_cards_db(cards_db)
    for category in CATEGORIES:
        write_card_file(
            os.path.join(exports_dir, f"collection_pauper_{category}.txt"),
            sorted(pauper_cards[category], key=lambda card: card[1].casefold()),
        )
        write_card_file(
            os.path.join(exports_dir, f"collection_non_pauper_{category}.txt"),
            sorted(non_pauper_cards[category], key=lambda card: card[1].casefold()),
        )
    print(
        "[Magic] Resumen: "
        f"cartas Pauper={counters['pauper']}, "
        f"no legales en Pauper={counters['nonlegal_pauper']}, "
        f"desconocidas={counters['unknown']}"
    )


def main():
    parser = argparse.ArgumentParser(description="Scrapea mazos de Magic desde mtgdecks.net.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignora la caché de mazos y vuelve a descargarlos.",
    )
    arguments = parser.parse_args()

    print("[Magic] Inicio del scraper")
    formats = load_formats()
    cache = load_deck_cache()
    decks = []
    for format_name, urls in formats:
        for url in urls:
            decks.append({
                "format": format_name,
                "name": deck_name_from_url(url),
                "url": url,
                "cards": scrape_deck(url, cache, refresh=arguments.refresh),
            })

    if not decks:
        print("No hay mazos configurados en decks/decks.yaml.")
        return

    cards_db = load_cards_db()
    print(f"[Magic] Caché de cartas cargada: {len(cards_db)} registros")
    process_decks(decks, cards_db)
    print(f"[Magic] Mazos procesados: {len(decks)}")


if __name__ == "__main__":
    main()
