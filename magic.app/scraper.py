import argparse
import json
import re
import time

import requests
from curl_cffi import requests as cffi_requests

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


def scrape_decks(urls):
    aggregated = {}
    for url in urls:
        txt_url = url.rstrip("/") + "/txt"
        print(f"-> {txt_url}")
        try:
            resp = cffi_requests.get(txt_url, impersonate="chrome")
        except Exception as e:
            print(f"  ! Error de red: {e}")
            continue
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code}")
            continue
        for line in resp.text.splitlines():
            parsed = parse_card_line(line)
            if not parsed:
                continue
            qty, name = parsed
            if name in BASIC_LANDS:
                continue
            aggregated[name] = max(aggregated.get(name, 0), qty)
    return aggregated


def write_export_counted(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(items):
            f.write(f"{items[name]} {name}\n")


def write_export_named(path, names):
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(names):
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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Mantiene los export_pauper_*.txt y export_unknown.txt existentes y solo agrega cartas nuevas (union aditiva, reorden alfabetico).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    urls = load_urls()
    all_cards = scrape_decks(urls)
    print(f"Cartas unicas (excluyendo basicas): {len(all_cards)}")

    if not all_cards:
        print("Sin cartas que procesar.")
        return

    cards_db = load_cards_db()

    buckets = {cat: {"pauper": set(), "nopauper": {}} for cat in CATEGORIES}
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
            buckets[category]["pauper"].add(name)
        else:
            buckets[category]["nopauper"][name] = all_cards[name]

    with open("cards_db.json", "w", encoding="utf-8") as f:
        json.dump(cards_db, f, indent=2, ensure_ascii=False)
        f.write("\n")

    for category in CATEGORIES:
        nopauper_path = f"export_nopauper_{category}.txt"
        write_export_counted(nopauper_path, buckets[category]["nopauper"])
        print(f"  {nopauper_path}: {len(buckets[category]['nopauper'])} cartas")

        pauper_path = f"export_pauper_{category}.txt"
        if args.keep:
            new_names = buckets[category]["pauper"]
            existing = set()
            try:
                with open(pauper_path, "r", encoding="utf-8") as f:
                    for line in f:
                        name = line.strip()
                        if name:
                            existing.add(name)
            except FileNotFoundError:
                pass
            merged = merge_named(pauper_path, new_names)
            write_export_named(pauper_path, merged)
            added = len(merged) - len(existing)
            print(f"  {pauper_path}: {len(merged)} cartas ({added} nuevas, {len(existing)} mantenidas)")
        else:
            write_export_named(pauper_path, buckets[category]["pauper"])
            print(f"  {pauper_path}: {len(buckets[category]['pauper'])} cartas")

    unknown_path = "export_unknown.txt"
    if args.keep:
        existing_unknown = set()
        try:
            with open(unknown_path, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if name:
                        existing_unknown.add(name)
        except FileNotFoundError:
            pass
        merged_unknown = merge_named(unknown_path, unknown)
        write_export_named(unknown_path, merged_unknown)
        added_u = len(merged_unknown) - len(existing_unknown)
        print(f"  {unknown_path}: {len(merged_unknown)} cartas ({added_u} nuevas, {len(existing_unknown)} mantenidas)")
    else:
        write_export_named(unknown_path, unknown)
        print(f"  {unknown_path}: {len(unknown)} cartas")


if __name__ == "__main__":
    main()
