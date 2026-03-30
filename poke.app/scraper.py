import requests
from bs4 import BeautifulSoup
import json
import re

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
                        if name not in all_cards[card_type]:
                            all_cards[card_type][name] = qty
                        else:
                            all_cards[card_type][name] += qty

with open('poke.cards.csv', 'w', encoding='utf-8') as f:
    f.write("Quantity,Name,Type\n")
    for card_type in ['Pokémon', 'Trainer', 'Energy']:
        for name, qty in sorted(all_cards[card_type].items()):
            f.write(f'{qty},"{name}","{card_type}"\n')

total = sum(sum(v.values()) for v in all_cards.values())
print(f"Guardado {total} cartas en poke.cards.csv")
print(f"  Pokémon: {sum(all_cards['Pokémon'].values())}")
print(f"  Trainer: {sum(all_cards['Trainer'].values())}")
print(f"  Energy: {sum(all_cards['Energy'].values())}")
