# tcg-scraper-python

Scripts de web scraping para construir bases de datos de cartas coleccionables.

## Descripción

Proyecto para extraer datos de cartas de Magic: The Gathering y Pokemon TCG desde diversas fuentes.

## Scrapers disponibles

- `magic.app/` - Magic: The Gathering
- `poke.app/` - Pokemon TCG

## Requisitos

```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
# Ejecutar todos los scrapers
python main.py

# Ejecutar un scraper específico
cd magic.app && python scraper.py
cd poke.app && python scraper.py
```

## Salida

- `magic.app/magic.cards.csv` - Cartas de Magic: The Gathering
- `poke.app/poke.cards.csv` - Cartas de Pokemon TCG

## Tech Stack

- [Python](https://www.python.org/) - Lenguaje de programación
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - Web scraping