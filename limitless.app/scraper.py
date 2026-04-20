import requests
from bs4 import BeautifulSoup
import json
import re

BASIC_ENERGIES = {
    "Fighting Energy", "Water Energy", "Fire Energy", "Grass Energy",
    "Lightning Energy", "Psychic Energy", "Darkness Energy",
    "Metal Energy", "Fairy Energy", "Colorless Energy"
}

with open('urls.json', 'r') as f:
    urls = json.load(f)

all_cards = {'Pokémon': {}, 'Trainer': {}, 'Energy': {}}

for url in urls:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    for column in soup.find_all('div', class_='column'):
        heading = column.find('div', class_='heading')
        if heading:
            heading_text = heading.text.strip()
            if heading_text.startswith('Pokémon'):
                card_type = 'Pokémon'
            elif heading_text.startswith('Trainer'):
                card_type = 'Trainer'
            elif heading_text.startswith('Energy'):
                card_type = 'Energy'
            else:
                continue

            for p in column.find_all('p'):
                link = p.find('a')
                if link:
                    text = link.text.strip()
                    match = re.match(r'^(\d+)\s+(.+)$', text)
                    if match:
                        qty = int(match.group(1))
                        name = match.group(2).strip()
                        if card_type == 'Energy' and name in BASIC_ENERGIES:
                            continue
                        all_cards[card_type][name] = max(all_cards[card_type].get(name, 0), qty)

all_flat = {}
for card_type in all_cards:
    for name, qty in all_cards[card_type].items():
        all_flat[name] = max(all_flat.get(name, 0), qty)

def parse_card_name(raw_name):
    m = re.match(r'^(.+?)\s+\(([A-Z0-9]+)-(\w+)\)$', raw_name, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).upper(), str(m.group(3))
    return raw_name, None, None

def get_owned(raw_name, db_entries):
    name, card_set, card_number = parse_card_name(raw_name)
    if card_set and card_number:
        for entry in db_entries:
            if (entry['name'] == name and
                    entry.get('card_set', '').upper() == card_set and
                    str(entry.get('card_number', '')) == card_number):
                return entry['quantity']
        return 0
    for entry in db_entries:
        if entry['name'] == name:
            return entry['quantity']
    return 0

db_entries = []
db_empty = True
try:
    with open('database.json', 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if content:
            data = json.loads(content)
            if data:
                db_entries = data
                db_empty = False
except FileNotFoundError:
    pass

if db_empty:
    export = all_flat.copy()
else:
    export = {name: all_flat[name] - get_owned(name, db_entries) for name in all_flat}
export = {name: qty for name, qty in export.items() if qty > 0}

with open('export.txt', 'w', encoding='utf-8') as f:
    for name in sorted(export):
        f.write(f"{export[name]} {name}\n")

print(f"Guardadas {len(export)} cartas en export.txt")
