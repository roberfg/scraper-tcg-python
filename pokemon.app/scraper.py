import json
import os
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

TRAINER_BUCKETS = ("supporters", "items", "tools", "stadiums")

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
                entry = (name, set_code, number, qty)
                for i, e in enumerate(aggregated[section]):
                    if e[0] == name and e[1] == set_code and e[2] == number:
                        if qty > e[3]:
                            aggregated[section][i] = entry
                        break
                else:
                    aggregated[section].append(entry)
    return aggregated


def read_collection(filename):
    aggregated = {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                m = re.match(r"^(\d+)\s+(.+)$", line)
                if not m:
                    continue
                qty = int(m.group(1))
                name = m.group(2).strip()
                aggregated[name] = aggregated.get(name, 0) + qty
    except FileNotFoundError:
        pass
    return aggregated


def write_collection_file(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(items):
            f.write(f"{items[name]} {name}\n")


def prompt_and_update(path, card_name, mazo_qty):
    existing = read_collection(path)
    if existing.get(card_name, 0) > 0:
        return max(0, mazo_qty - existing[card_name])

    while True:
        try:
            resp = input(f"  ¿Tienes '{card_name}'? (Enter=no la tengo, número=cantidad): ").strip()
        except EOFError:
            return mazo_qty
        if resp == "":
            return mazo_qty
        try:
            qty = int(resp)
            if qty < 0:
                print("  La cantidad no puede ser negativa.")
                continue
        except ValueError:
            print("  Entrada no válida, escribe un número o Enter.")
            continue
        existing[card_name] = existing.get(card_name, 0) + qty
        write_collection_file(path, existing)
        return max(0, mazo_qty - qty)


def write_named(path, names):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(set(names)):
            f.write(f"{name}\n")


def write_buylist(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(items):
            f.write(f"{items[name]} {name}\n")


def write_pokemon(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for name, set_code, number, qty in sorted(items, key=lambda x: x[0]):
            if set_code and number:
                f.write(f"{qty} {name} ({set_code}-{number})\n")
            else:
                f.write(f"{qty} {name}\n")


def main():
    urls = load_urls()
    aggregated = scrape_decks(urls)
    total = sum(len(v) for v in aggregated.values())
    print(f"Cartas unicas scrapeadas: {total}")

    if total == 0:
        print("Sin cartas que procesar.")
        return

    cards_db = load_cards_db()

    supporters, items, tools, stadiums, trainer_unknown = [], [], [], [], []
    for name, set_code, number, _qty in aggregated["Trainer"]:
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

    energy_names = [name for name, _set, _num, _qty in aggregated["Energy"]]

    buylist_pokemon = {}
    for name, _set, _num, qty in aggregated["Pokemon"]:
        needed = prompt_and_update("collection_pokemon.txt", name, qty)
        if needed > 0:
            buylist_pokemon[name] = buylist_pokemon.get(name, 0) + needed

    buylist_trainers = {}
    trainer_qtys = {name: qty for name, _set, _num, qty in aggregated["Trainer"]}
    trainer_coll_path = {}
    for name in supporters:
        trainer_coll_path[name] = "collection_supporters.txt"
    for name in items:
        trainer_coll_path[name] = "collection_items.txt"
    for name in tools:
        trainer_coll_path[name] = "collection_tools.txt"
    for name in stadiums:
        trainer_coll_path[name] = "collection_stadiums.txt"
    unknown_set = set(trainer_unknown)
    for name, mazo_qty in trainer_qtys.items():
        if name in unknown_set:
            continue
        coll_path = trainer_coll_path.get(name)
        if coll_path is None:
            continue
        needed = prompt_and_update(coll_path, name, mazo_qty)
        if needed > 0:
            buylist_trainers[name] = buylist_trainers.get(name, 0) + needed

    for name, _set, _num, qty in aggregated["Energy"]:
        needed = prompt_and_update("collection_energies.txt", name, qty)
        if needed > 0:
            buylist_trainers[name] = buylist_trainers.get(name, 0) + needed

    write_buylist("buylist_pokemon.txt", buylist_pokemon)
    print(f"  buylist_pokemon.txt: {len(buylist_pokemon)} cartas")

    write_buylist("buylist_trainers.txt", buylist_trainers)
    print(f"  buylist_trainers.txt: {len(buylist_trainers)} cartas")

    write_named("export_unknown.txt", trainer_unknown)
    print(f"  export_unknown.txt: {len(set(trainer_unknown))} cartas")


if __name__ == "__main__":
    main()
