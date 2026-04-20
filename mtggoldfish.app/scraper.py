import requests
import re
import json

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

with open('urls.json', 'r') as f:
    urls = json.load(f)

all_cards = {}

for url in urls:
    # Extraer el ID del deck de la URL (ej: /deck/7730058 o /deck/7730058#paper)
    match = re.search(r'/deck/(\d+)', url)
    if not match:
        print(f"No se pudo extraer ID de {url}")
        continue

    deck_id = match.group(1)
    download_url = f"https://www.mtggoldfish.com/deck/download/{deck_id}"

    response = requests.get(download_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error {response.status_code} en {download_url}")
        continue

    for line in response.text.splitlines():
        line = line.strip()
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
        content = f.read().strip()
        if content:
            data = json.loads(content)
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
