import requests
from bs4 import BeautifulSoup
import re
import json
import time

with open('urls.json', 'r') as f:
    urls = json.load(f)

all_cards = {}

for url in urls:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    breakdown = soup.find('div', class_='deck-archetype-breakdown')
    if breakdown:
        for container in breakdown.find_all('div', class_='spoiler-card-container'):
            heading = container.find('h3')
            if heading:
                card_type = heading.text.strip()
                
                for card in container.find_all('div', class_='spoiler-card'):
                    img = card.find('img')
                    if img and img.get('alt'):
                        name = img['alt'].strip()
                        if name and name not in all_cards:
                            all_cards[name] = card_type

print(f"Encontradas {len(all_cards)} cartas, buscando tipos en Scryfall...")

scryfall_types = {}
for i, card_name in enumerate(all_cards.keys(), 1):
    try:
        clean_name = card_name.split('[')[0].strip()
        response = requests.get(
            f'https://api.scryfall.com/cards/named',
            params={'fuzzy': clean_name}
        )
        if response.status_code == 200:
            data = response.json()
            scryfall_types[card_name] = data.get('type_line', '')
        elif response.status_code == 404:
            scryfall_types[card_name] = 'Unknown'
        else:
            scryfall_types[card_name] = ''
        
        print(f"[{i}/{len(all_cards)}] {card_name} -> {scryfall_types[card_name]}")
        time.sleep(0.1)
    except Exception as e:
        print(f"Error con {card_name}: {e}")
        scryfall_types[card_name] = ''

with open('magic.cards.csv', 'w', encoding='utf-8') as f:
    f.write("Name,Type\n")
    for name, card_type in sorted(all_cards.items()):
        f.write(f'"{name}","{scryfall_types.get(name, "")}"\n')

print(f"\nGuardado {len(all_cards)} cartas en magic.cards.csv")
