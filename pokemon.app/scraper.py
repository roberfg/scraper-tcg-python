import argparse
import json
import re
import time

import requests
from bs4 import BeautifulSoup

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

HEADERS = {
    "User-Agent": "pokemon-app/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_card_text(text):
    m = re.match(r"^(\d+)\s+(.+)$", text.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


def parse_card_href(href):
    m = re.search(r"/cards/([A-Za-z0-9]+)/(\d+)", href or "")
    if not m:
        return None
    return m.group(1).upper(), m.group(2)


def parse_card_type_text(raw):
    m = re.match(r"^\s*(\w+)\s*(?:-\s*(\w+))?\s*$", raw)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def load_urls():
    with open("urls.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards_db():
    try:
        with open("cards_db.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def fetch_card_subtype(name, set_code, number, cards_db):
    cache_key = f"{name}|{set_code}|{number}"
    if cache_key in cards_db:
        return cards_db[cache_key], True

    url = f"https://limitlesstcg.com/cards/{set_code}/{number}"
    backoffs = [2, 4, 8, 16, 30, 30]
    for attempt, wait in enumerate(backoffs, start=1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            print(f"  ! Error de red con '{name}': {e}")
            return None, False
        if resp.status_code == 429:
            print(f"  ! Rate limit (429) en '{name}'; esperando {wait}s (intento {attempt}/{len(backoffs)})...")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            return None, False
        break
    else:
        return None, False

    soup = BeautifulSoup(resp.text, "html.parser")
    type_p = soup.select_one("p.card-text-type")
    if not type_p:
        return None, False
    supertype, subtype = parse_card_type_text(type_p.get_text(" ", strip=True))
    info = {"supertype": supertype, "subtype": subtype}
    cards_db[cache_key] = info
    return info, False


def detect_section(heading_text):
    if heading_text.startswith("Pok"):
        return "Pokemon"
    if heading_text.startswith("Trainer"):
        return "Trainer"
    if heading_text.startswith("Energy"):
        return "Energy"
    return None


def scrape_decks(urls):
    aggregated = {"Pokemon": [], "Trainer": [], "Energy": []}

    for url in urls:
        print(f"-> {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            print(f"  ! Error de red: {e}")
            continue
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code}")
            continue
        soup = BeautifulSoup(resp.content, "html.parser")
        for column in soup.find_all("div", class_="column"):
            heading = column.find("div", class_="heading")
            if not heading:
                continue
            section = detect_section(heading.get_text(strip=True))
            if not section:
                continue
            for p in column.find_all("p"):
                link = p.find("a")
                if not link:
                    continue
                parsed = parse_card_text(link.get_text())
                if not parsed:
                    continue
                qty, name = parsed
                href_info = parse_card_href(link.get("href", ""))
                if not href_info:
                    continue
                set_code, number = href_info
                if section == "Energy" and name in BASIC_ENERGIES:
                    continue
                key = (name, set_code, number)
                for i, (k, q) in enumerate(aggregated[section]):
                    if k == key:
                        if qty > q:
                            aggregated[section][i] = (key, qty)
                        break
                else:
                    aggregated[section].append((key, qty))
    return aggregated


def write_named(path, names):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(set(names)):
            f.write(f"{name}\n")


def merge_named(path, new_names):
    existing = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    existing.add(name)
    except FileNotFoundError:
        pass
    return sorted(existing | set(new_names))


def write_pokemon(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for (name, set_code, number), qty in sorted(items, key=lambda x: x[0][0]):
            f.write(f"{qty} {name} ({set_code}-{number})\n")


def read_existing(path):
    existing = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    existing.add(name)
    except FileNotFoundError:
        pass
    return existing


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Mantiene export_supporters.txt, export_items.txt, export_tools.txt, export_stadiums.txt y export_energies.txt existentes y solo agrega cartas nuevas (union aditiva, reorden alfabetico).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    urls = load_urls()
    aggregated = scrape_decks(urls)
    total = sum(len(v) for v in aggregated.values())
    print(f"Cartas unicas scrapeadas: {total}")

    if total == 0:
        print("Sin cartas que procesar.")
        return

    cards_db = load_cards_db()

    supporters, items, tools, stadiums, trainer_unknown = [], [], [], [], []
    for key, _qty in aggregated["Trainer"]:
        name, set_code, number = key
        info, was_cached = fetch_card_subtype(name, set_code, number, cards_db)
        if not was_cached:
            time.sleep(0.12)
        if info is None or info.get("supertype") != "Trainer" or info.get("subtype") is None:
            trainer_unknown.append(name)
            continue
        bucket = SUBTYPE_TO_BUCKET.get(info["subtype"])
        if bucket == "supporters":
            supporters.append(name)
        elif bucket == "items":
            items.append(name)
        elif bucket == "tools":
            tools.append(name)
        elif bucket == "stadiums":
            stadiums.append(name)
        else:
            trainer_unknown.append(name)

    with open("cards_db.json", "w", encoding="utf-8") as f:
        json.dump(cards_db, f, indent=2, ensure_ascii=False)
        f.write("\n")

    write_pokemon("export_pokemon.txt", aggregated["Pokemon"])
    print(f"  export_pokemon.txt: {len(aggregated['Pokemon'])} cartas")

    write_named("export_trainer_unknown.txt", trainer_unknown)
    print(f"  export_trainer_unknown.txt: {len(set(trainer_unknown))} cartas")

    energy_names = [key[0] for key, _ in aggregated["Energy"]]
    keep_paths = {
        "export_supporters.txt": supporters,
        "export_items.txt": items,
        "export_tools.txt": tools,
        "export_stadiums.txt": stadiums,
        "export_energies.txt": energy_names,
    }
    for path, names in keep_paths.items():
        if args.keep:
            existing = read_existing(path)
            merged = merge_named(path, names)
            write_named(path, merged)
            added = len(merged) - len(existing)
            print(f"  {path}: {len(merged)} cartas ({added} nuevas, {len(existing)} mantenidas)")
        else:
            write_named(path, names)
            print(f"  {path}: {len(set(names))} cartas")


if __name__ == "__main__":
    main()
