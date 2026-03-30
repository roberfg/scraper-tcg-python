# tcg-scraper-python

Web scraping scripts for building a card collector's database.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

Run all scrapers:

```bash
python main.py
```

Or run individually:

```bash
cd magic.app && python scraper.py
cd poke.app && python scraper.py
```

## Output

- `magic.app/magic.cards.csv` - Magic: The Gathering cards with type
- `poke.app/poke.cards.csv` - Pokemon TCG cards with quantity and type