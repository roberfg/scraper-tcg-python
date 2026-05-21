import json
import os
import re
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URLS_JSON = os.path.join(BASE_DIR, 'urls.json')
EXPORT_TXT = os.path.join(BASE_DIR, 'export.txt')

SECTION_RE = re.compile(r'^(Pok[éeè]mon|Trainer|Energy)\s*:\s*\d+$')
SECTION_MAP = {'Pokémon': 'Pokémon', 'Pokemon': 'Pokémon', 'Pokèmon': 'Pokémon', 'Trainer': 'Trainer', 'Energy': 'Energy'}

with open(URLS_JSON, 'r', encoding='utf-8') as f:
    urls = json.load(f)

cards = {'Pokémon': set(), 'Trainer': set(), 'Energy': set()}

for url in urls:
    print(f"Scrapeando {url} ...")
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    for item in soup.select('li.accordion-item'):
        desc = item.select_one('[data-sqsp-accordion-block-item-description]')
        if not desc:
            continue

        current_section = None
        for p in desc.find_all('p'):
            line = p.get_text(strip=True)
            if not line:
                continue
            m = SECTION_RE.match(line)
            if m:
                current_section = SECTION_MAP.get(m.group(1))
                continue
            if current_section:
                cards[current_section].add(line)

groups = []
for section in ['Pokémon', 'Trainer', 'Energy']:
    if cards[section]:
        groups.append('\n'.join(sorted(cards[section])))

with open(EXPORT_TXT, 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(groups) + '\n')

total = sum(len(s) for s in cards.values())
print(f"Exportadas {total} cartas únicas a export.txt")
