import re
import json
import csv

BASIC_LANDS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest",
    "Snow-Covered Plains", "Snow-Covered Island",
    "Snow-Covered Swamp", "Snow-Covered Mountain",
    "Snow-Covered Forest", "Wastes",
}

def parse_line(line):
    line = re.sub(r'^SB:\s*', '', line, flags=re.IGNORECASE)

    m = re.match(r'^(\d+)\s*x?\s*(.+)$', line)
    if not m:
        return None

    qty = int(m.group(1))
    rest = m.group(2).strip()

    m2 = re.match(r'^(.+?)\s*\(([A-Z0-9]{2,5})\)\s*#?(\d+)\s*$', rest)
    if m2:
        return {
            'quantity': qty,
            'name': m2.group(1).strip().rstrip(','),
            'set_code': m2.group(2),
            'collector_number': m2.group(3),
        }

    m3 = re.match(r'^(.+?)\s*\(([A-Z0-9]{2,5})\)\s*$', rest)
    if m3:
        return {
            'quantity': qty,
            'name': m3.group(1).strip().rstrip(','),
            'set_code': m3.group(2),
            'collector_number': '',
        }

    return {
        'quantity': qty,
        'name': rest.rstrip(','),
        'set_code': '',
        'collector_number': '',
    }


def parse_decklist(text):
    cards = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(//|#|Sideboard|SB$)', line, re.IGNORECASE):
            continue

        card = parse_line(line)
        if card and card['name'] not in BASIC_LANDS:
            cards.append(card)
    return cards


def aggregate(cards):
    grouped = {}
    for c in cards:
        key = (c['name'], c.get('set_code', ''), c.get('collector_number', ''))
        if key in grouped:
            grouped[key] = max(grouped[key], c['quantity'])
        else:
            grouped[key] = c['quantity']

    result = []
    for (name, set_code, coll), qty in sorted(grouped.items()):
        result.append({'name': name, 'quantity': qty, 'set_code': set_code, 'collector_number': coll})
    return result


with open('decks.txt', 'r', encoding='utf-8') as f:
    content = f.read()

cards = parse_decklist(content)
aggregated = aggregate(cards)

db = {}
try:
    with open('database.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        if data:
            for entry in data:
                db[entry['name']] = db.get(entry['name'], 0) + entry['quantity']
except (FileNotFoundError, json.JSONDecodeError):
    pass

with open('export.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Count', 'Name', 'SetCode', 'CollectorNumber'])
    written = 0
    for card in aggregated:
        qty = card['quantity'] - db.get(card['name'], 0)
        if qty > 0:
            writer.writerow([qty, card['name'], card['set_code'], card['collector_number']])
            written += 1

print(f"Exportadas {written} cartas a export.csv (formato Moxfield)")
