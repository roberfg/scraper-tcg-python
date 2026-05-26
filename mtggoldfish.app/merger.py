import json
import re

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

with open('decks.txt', 'r', encoding='utf-8') as f:
    content = f.read()

decks_text = content.strip().split('\n\n')
all_cards = {}

for deck_text in decks_text:
    if not deck_text.strip():
        continue
    for line in deck_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(\d+)\s+(.+)$', line)
        if m:
            qty = int(m.group(1))
            name = m.group(2).strip()
            if name not in BASIC_LANDS:
                all_cards[name] = max(all_cards.get(name, 0), qty)

db = {}
db_empty = True
try:
    with open('database.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        if data:
            for entry in data:
                db[entry['name']] = entry['quantity']
            db_empty = False
except FileNotFoundError:
    pass

if db_empty:
    export = all_cards.copy()
else:
    export = {name: all_cards[name] - db.get(name, 0) for name in all_cards}
export = {name: qty for name, qty in export.items() if qty > 0}

with open('export.txt', 'w', encoding='utf-8') as f:
    for name in sorted(export):
        f.write(f"{export[name]} {name}\n")

print(f"Guardadas {len(export)} cartas en export.txt")
