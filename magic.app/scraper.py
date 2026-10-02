import json
import os
import re
import time
import unicodedata

import requests
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


def load_decks(path="decks/decks.yaml"):
    print(f"[Magic] Cargando configuración de mazos: {path}")
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    decks_by_format = data.get("decks") if isinstance(data, dict) else None
    if not isinstance(decks_by_format, dict):
        raise ValueError(f"{path} debe contener un objeto 'decks'.")

    decks_dir = os.path.dirname(path) or "."
    decks = []
    for format_name, named_decks in decks_by_format.items():
        if not isinstance(format_name, str) or not isinstance(named_decks, dict):
            raise ValueError("Cada formato debe contener un mapa de nombre de mazo a archivo.")
        for deck_name, file_stem in named_decks.items():
            if not isinstance(deck_name, str) or not isinstance(file_stem, str) or not file_stem.strip():
                raise ValueError("Cada mazo debe tener un nombre y un archivo válido.")

            file_path = os.path.join(decks_dir, file_stem.strip() + ".txt")
            if not os.path.isfile(file_path):
                raise FileNotFoundError(
                    f"No existe el archivo del mazo '{deck_name}' "
                    f"(formato '{format_name}'): {file_path}"
                )

            decks.append({
                "format": format_name,
                "name": deck_name,
                "path": file_path,
            })
    print(f"[Magic] Mazos cargados: {len(decks)}")
    return decks


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
        deck_cards.append((deck, read_deck_file(deck["path"])))

    clear_exports(exports_dir)
    pauper_cards = {category: [] for category in CATEGORIES}
    pauper_indexes = {category: {} for category in CATEGORIES}
    unknown_cards = []
    unknown_seen = set()
    pauper_nonlegal_cards = []
    first_occurrences = {}
    counters = {"pauper": 0, "nonlegal_pauper": 0, "unknown": 0, "deck": 0}

    for deck, cards in deck_cards:
        is_pauper_deck = deck["format"].lower() == "pauper"
        print(
            f"[Magic] Procesando {deck['format']}/{deck['name']} "
            f"({len(cards)} cartas, pauper={is_pauper_deck})"
        )
        output_cards = []
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
                print(f"    [Magic] Destino: collection_{category}.txt")
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

            if is_pauper_deck:
                print("    [Magic] Destino: review_pauper_nonlegal.txt")
                pauper_nonlegal_cards.append([
                    quantity,
                    name,
                    deck_filename(deck).removesuffix(".txt"),
                ])
                counters["nonlegal_pauper"] += 1
                continue

            reference = None
            if name in first_occurrences:
                first_quantity, first_deck = first_occurrences[name]
                reference = f"{first_quantity} en {deck_filename(first_deck).removesuffix('.txt')}"
            else:
                first_occurrences[name] = (quantity, deck)
            output_cards.append([quantity, name, reference])

        if is_pauper_deck:
            print(f"[Magic] No se genera deck_pauper para {deck['name']}")
        else:
            write_card_file(os.path.join(exports_dir, deck_filename(deck)), output_cards)
            counters["deck"] += 1

    write_cards_db(cards_db)
    for category in CATEGORIES:
        write_card_file(
            os.path.join(exports_dir, f"collection_{category}.txt"),
            sorted(pauper_cards[category], key=lambda card: card[1].casefold()),
        )
    with open(os.path.join(exports_dir, "unknown.txt"), "w", encoding="utf-8") as file:
        for name in unknown_cards:
            file.write(f"{name}\n")
    print(f"[Magic] Generado {os.path.join(exports_dir, 'unknown.txt')}: {len(unknown_cards)} registros")
    write_card_file(
        os.path.join(exports_dir, "review_pauper_nonlegal.txt"),
        pauper_nonlegal_cards,
    )
    print(
        "[Magic] Resumen: "
        f"cartas Pauper={counters['pauper']}, "
        f"no legales en Pauper={counters['nonlegal_pauper']}, "
        f"desconocidas={counters['unknown']}, "
        f"decks exportados={counters['deck']}"
    )


def main():
    print("[Magic] Inicio del scraper")
    decks = load_decks()
    if not decks:
        print("No hay mazos configurados en decks/decks.yaml.")
        return

    cards_db = load_cards_db()
    print(f"[Magic] Caché de cartas cargada: {len(cards_db)} registros")
    process_decks(decks, cards_db)
    print(f"[Magic] Mazos procesados: {len(decks)}")


if __name__ == "__main__":
    main()
