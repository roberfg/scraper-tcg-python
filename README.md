# tcg-scraper-python

Scripts de web scraping para construir listas de cartas coleccionables de Magic: The Gathering y Pokémon TCG, clasificadas automáticamente y listas para comprar.

## Descripción

El proyecto contiene dos scrapers independientes:

- **`magic.app/`**: scrapea mazos de Magic desde `mtgdecks.net`, suma las cantidades del sideboard al main por mazo, y clasifica cada carta como **pauper / no-pauper** y por **tipo** (criatura, instantáneo/conjuro, planeswalker, artefacto, encantamiento, tierra) consultando la API de Scryfall. Tierras básicas se ignoran.
- **`pokemon.app/`**: scrapea decklists de Pokémon desde Limitless TCG, separa Pokémon de Trainers, y subclasifica los Trainers en **Supporter / Item / Tool / Stadium** consultando `limitlesstcg.com` (que expone el subtipo de cada carta). Energías básicas se ignoran.

## Scrapers disponibles

| Carpeta | Juego | Fuente |
|---|---|---|
| `magic.app/` | Magic: The Gathering | mtgdecks.net + Scryfall |
| `pokemon.app/` | Pokemon TCG | play.limitlesstcg.com + limitlesstcg.com |

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

Dependencias principales: `requests`, `beautifulsoup4`, `curl_cffi` (bypass Cloudflare para `mtgdecks.net`).

## Configuración

Cada carpeta contiene un archivo `urls.json` con las URLs de los mazos/decklists a scrapear. Edítalo para agregar o quitar entradas.

## Uso

```bash
# Magic
cd magic.app && python scraper.py

# Pokémon
cd pokemon.app && python scraper.py
```

## Salida

### `magic.app`

Genera 12 archivos de export más uno adicional:

- `export_pauper_creatures.txt`, `export_pauper_spells.txt`, `export_pauper_planeswalkers.txt`, `export_pauper_artifacts.txt`, `export_pauper_enchantments.txt`, `export_pauper_lands.txt`
- `export_nopauper_creatures.txt`, `export_nopauper_spells.txt`, `export_nopauper_planeswalkers.txt`, `export_nopauper_artifacts.txt`, `export_nopauper_enchantments.txt`, `export_nopauper_lands.txt`
- `export_unknown.txt` (cartas que Scryfall no pudo resolver)

Cada archivo contiene una línea por carta, ordenado alfabéticamente, con dos formatos posibles:
- `export_pauper_*.txt` y `export_unknown.txt`: solo el nombre de la carta (una línea por carta única). Al comprar, se asume playset de 4 copias.
- `export_nopauper_*.txt`: formato `<cantidad> <nombre>`, donde la cantidad es la máxima vista entre los mazos (sumando main + sideboard por mazo).

La prioridad de tipos cuando una carta tiene varios (p.ej. *Artifact Creature*) es: Creature > Land > Planeswalker > Instant/Sorcery > Artifact > Enchantment.

**Cache local:** `cards_db.json` guarda `{nombre: {is_pauper, type_category}}` para evitar llamadas repetidas a Scryfall en ejecuciones sucesivas. Este archivo forma parte del repo (no se ignora en git) y nunca debe borrarse manualmente: se actualiza automáticamente al final de cada ejecución.

**Uso:**
```bash
cd magic.app
# Editar urls.json con las URLs de mtgdecks.net a procesar
python scraper.py
```

**Flags CLI:**
- `--keep`: en lugar de sobrescribir `export_pauper_*.txt` y `export_unknown.txt`, lee los archivos existentes y los reescribe con la unión de las cartas previas y las nuevas (orden alfabético, sin duplicados, sin eliminar nada). El resto de archivos (`export_nopauper_*.txt`, `cards_db.json`) se sobreescriben normalmente.

```bash
python scraper.py --keep
```

### `pokemon.app`

Scrapea decklists de Limitless TCG (`play.limitlesstcg.com/.../decklist`) y separa las cartas en Pokémon y Trainers. Los Trainers se subclasifican en **Supporter / Item / Tool / Stadium** consultando la base de datos de `limitlesstcg.com` (que sí expone el subtipo en el HTML de cada carta). Las energías básicas se ignoran.

Genera 6 archivos de export más uno adicional:

- `export_pokemon.txt`
- `export_supporters.txt`, `export_items.txt`, `export_tools.txt`, `export_stadiums.txt`
- `export_energies.txt`
- `export_trainer_unknown.txt` (Trainers cuyo subtipo no se pudo determinar)

Formatos de export:
- `export_pokemon.txt`: una línea por carta con formato `<cantidad> <nombre> (<SET>-<número>)`, p.ej. `3 Okidogi (TWM-111)`.
- Resto: una línea por carta con **solo el nombre**, ordenado alfabéticamente.

**Cache local:** `cards_db.json` guarda `{nombre|set|numero: {supertype, subtype}}` para evitar llamadas repetidas a `limitlesstcg.com`. Este archivo forma parte del repo (no se ignora en git) y nunca debe borrarse manualmente.

**Uso:**
```bash
cd pokemon.app
# Editar urls.json con las URLs de play.limitlesstcg.com a procesar
python scraper.py
```

**Flags CLI:**
- `--keep`: en lugar de sobrescribir `export_supporters.txt`, `export_items.txt`, `export_tools.txt`, `export_stadiums.txt` y `export_energies.txt`, lee los archivos existentes y los reescribe con la unión de las cartas previas y las nuevas (orden alfabético, sin duplicados, sin eliminar nada). El resto de archivos (`export_pokemon.txt`, `export_trainer_unknown.txt`, `cards_db.json`) se sobreescriben normalmente.

```bash
python scraper.py --keep
```

## Tech Stack

- [Python](https://www.python.org/) - Lenguaje de scripting.
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - Parseo de HTML.
- [Requests](https://requests.readthedocs.io/) - Peticiones HTTP.
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - Bypass de protección Cloudflare (`mtgdecks.net`).
- [Scryfall API](https://scryfall.com/docs/api) - Datos y legalidades de cartas de Magic.
- [Limitless TCG](https://limitlesstcg.com) - Decks y datos de cartas de Pokémon.
