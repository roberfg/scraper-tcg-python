import json
import os
import re
import time

import requests

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


def parse_card_line(line):
    line = re.sub(r"^SB:\s*", "", line, flags=re.IGNORECASE).strip()
    m = re.match(r"^(\d+)\s+x?\s*(.+)$", line)
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip().rstrip(",")


def classify_type(type_line):
    tl = type_line or ""
    if "Creature" in tl:
        return "creatures"
    if "Land" in tl:
        return "lands"
    if "Planeswalker" in tl:
        return "planeswalkers"
    if "Instant" in tl or "Sorcery" in tl:
        return "spells"
    if "Artifact" in tl:
        return "artifacts"
    if "Enchantment" in tl:
        return "enchantments"
    return None


def fetch_card_info(name, cards_db):
    if name in cards_db:
        return cards_db[name], True

    url = "https://api.scryfall.com/cards/named?exact=" + requests.utils.quote(name)
    backoffs = [2, 4, 8, 16, 30, 30]
    for attempt, wait in enumerate(backoffs, start=1):
        try:
            resp = requests.get(url, headers=SCRYFALL_HEADERS, timeout=15)
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

    data = resp.json()
    if data.get("object") == "error":
        return None, False

    if data.get("card_faces"):
        faces_type_lines = [f.get("type_line", "") for f in data["card_faces"]]
        type_line = " // ".join([t for t in faces_type_lines if t]) or data.get("type_line", "")
    else:
        type_line = data.get("type_line", "")

    is_pauper = data.get("legalities", {}).get("pauper") == "legal"
    category = classify_type(type_line)
    info = {"is_pauper": is_pauper, "type_category": category}
    cards_db[name] = info
    return info, False


def load_cards_db():
    try:
        with open("cards_db.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def read_deck_file(path):
    aggregated = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"  ! Archivo no encontrado: {path}")
        return aggregated
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        parsed = parse_card_line(line)
        if not parsed:
            continue
        qty, name = parsed
        if name in BASIC_LANDS:
            continue
        aggregated[name] = max(aggregated.get(name, 0), qty)
    return aggregated


def read_decks_from_dir(decks_dir="decks"):
    if not os.path.isdir(decks_dir):
        print(f"  ! Carpeta no encontrada: {decks_dir}")
        return {}
    aggregated = {}
    files = sorted(f for f in os.listdir(decks_dir) if f.endswith(".txt"))
    if not files:
        print(f"  ! No hay archivos .txt en {decks_dir}/")
        return aggregated
    for filename in files:
        path = os.path.join(decks_dir, filename)
        print(f"-> file: {path}")
        partial = read_deck_file(path)
        for name, qty in partial.items():
            aggregated[name] = max(aggregated.get(name, 0), qty)
    return aggregated


def read_collection(category, kind):
    path = f"collection_{kind}_{category}.txt"
    aggregated = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                parsed = parse_card_line(line)
                if not parsed:
                    continue
                qty, name = parsed
                aggregated[name] = aggregated.get(name, 0) + qty
    except FileNotFoundError:
        pass
    return aggregated


def read_collection_file(path):
    aggregated = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
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
    existing = read_collection_file(path)
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


def write_buylist(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(items):
            f.write(f"{items[name]} {name}\n")


def main():
    all_cards = read_decks_from_dir("decks")
    print(f"Cartas unicas (excluyendo basicas): {len(all_cards)}")

    if not all_cards:
        print("Sin cartas que procesar.")
        return

    cards_db = load_cards_db()

    buckets = {cat: {"pauper": {}, "nopauper": {}} for cat in CATEGORIES}
    unknown = set()

    for name in sorted(all_cards):
        info, was_cached = fetch_card_info(name, cards_db)
        if not was_cached:
            time.sleep(0.12)
        if info is None or info.get("type_category") is None:
            unknown.add(name)
            continue
        category = info["type_category"]
        if category not in buckets:
            unknown.add(name)
            continue
        if info["is_pauper"]:
            buckets[category]["pauper"][name] = all_cards[name]
        else:
            buckets[category]["nopauper"][name] = all_cards[name]

    with open("cards_db.json", "w", encoding="utf-8") as f:
        json.dump(cards_db, f, indent=2, ensure_ascii=False)
        f.write("\n")

    buylist_pauper = {}
    buylist_nopauper = {}

    for category in CATEGORIES:
        coll_path_p = f"collection_pauper_{category}.txt"
        for name, mazo_qty in buckets[category]["pauper"].items():
            needed = prompt_and_update(coll_path_p, name, mazo_qty)
            if needed > 0:
                buylist_pauper[name] = buylist_pauper.get(name, 0) + needed

        coll_path_np = f"collection_nopauper_{category}.txt"
        for name, mazo_qty in buckets[category]["nopauper"].items():
            needed = prompt_and_update(coll_path_np, name, mazo_qty)
            if needed > 0:
                buylist_nopauper[name] = buylist_nopauper.get(name, 0) + needed

    write_buylist("buylist_pauper.txt", buylist_pauper)
    print(f"  buylist_pauper.txt: {len(buylist_pauper)} cartas")

    write_buylist("buylist_nopauper.txt", buylist_nopauper)
    print(f"  buylist_nopauper.txt: {len(buylist_nopauper)} cartas")

    if unknown:
        with open("export_unknown.txt", "w", encoding="utf-8") as f:
            for name in sorted(unknown):
                f.write(f"{name}\n")
        print(f"  export_unknown.txt: {len(unknown)} cartas")


if __name__ == "__main__":
    main()
