# tcg-scraper-python

Scripts de web scraping para construir listas de cartas coleccionables.

## Descripción

Proyecto para extraer datos de cartas de Magic: The Gathering y Pokemon TCG desde diversas fuentes. Cada scraper consolida listas de mazos, filtra cartas básicas/energías básicas, conserva la cantidad máxima vista por carta entre todos los mazos y exporta una lista ordenada alfabéticamente con las cartas que aún faltan adquirir.

## Scrapers disponibles

| Carpeta | Juego | Fuente |
|---|---|---|---|
| `limitless.app/` | Pokemon TCG | play.limitlesstcg.com |
| `glc.app/` | Pokemon TCG (Gym Leader Challenge) | gymleaderchallenge.com |
| `mtgdecks.app/` | Magic: The Gathering | mtgdecks.net |
| `mtggoldfish.app/` | Magic: The Gathering | mtggoldfish.com |
| `moxfield.app/` | Magic: The Gathering | Convierte exports de Magic a CSV para importar en moxfield.com |

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

## Configuración

Cada carpeta contiene un archivo `urls.json` con las URLs de los mazos a scrapear. Edítalo para agregar o quitar mazos.

Opcionalmente, puedes crear un archivo `database.json` con las cartas que ya posees (formato: `[{"name": "...", "quantity": N}]`). El scraper resta estas cantidades del resultado antes de exportar. Esto aplica en `limitless.app/`, `mtgdecks.app/` y `mtggoldfish.app/`; `glc.app/` no soporta base de datos propia.

## Uso

```bash
# Ejecutar un scraper específico
cd limitless.app && python scraper.py
cd glc.app && python scraper.py
cd mtgdecks.app && python scraper.py
cd mtggoldfish.app && python scraper.py
cd moxfield.app && python scraper.py
```

## Salida

Cada scraper genera un archivo `export.txt` dentro de su carpeta con las cartas que faltan adquirir, en el formato:

```
<cantidad> <nombre de carta>
```

La cantidad refleja la diferencia entre lo que requieren los mazos y lo que ya está registrado en `database.json`. Si una carta ya está completa en la base de datos, no aparece en el export.

Ejemplo:

```
2 Air Balloon
4 Applin (SCR-12)
3 Drakuloak (TWM-129)
```

### `moxfield.app`

A diferencia de los otros scrapers, `moxfield.app` no obtiene datos desde URLs, sino que convierte una lista de cartas desde un archivo de texto (`decks.txt`) al formato CSV que acepta Moxfield para importación de mazos.

**Formato de entrada (`decks.txt`):**
Soporta múltiples formatos de export de Magic:

- `4 Lightning Bolt` (solo cantidad + nombre)
- `4 Lightning Bolt (M10)` (con código de set)
- `4 Lightning Bolt (M10) 123` (MTGA, con código de set y número de colección)
- `4x Lightning Bolt` (con `x`)
- `SB: 1 Surgical Extraction` (sideboard, se incluye en el total)

Ignora cartas de tierra básica (Plains, Island, Swamp, Mountain, Forest y variantes).

**Salida (`export.csv`):** Archivo CSV con columnas `Count,Name,SetCode,CollectorNumber` listo para importar en Moxfield.

**Configuración opcional:** Soporta `database.json` para restar cartas que ya posees (mismo formato que las otras apps).

**Uso:**
```bash
cd moxfield.app
# Editar decks.txt con la lista de cartas a convertir
python scraper.py
# El resultado se guarda en export.csv
```

## Tech Stack

- [Python](https://www.python.org/) - Lenguaje de programación
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - Parseo de HTML
- [Requests](https://requests.readthedocs.io/) - Peticiones HTTP
- [Cloudscraper](https://github.com/VeNoMouS/cloudscraper) - Bypass de protección Cloudflare (mtgdecks)
