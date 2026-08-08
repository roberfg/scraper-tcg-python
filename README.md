# tcg-scraper-python

Scripts para construir listas de cartas coleccionables de Magic: The Gathering y Pokémon TCG, clasificadas automáticamente y listas para comprar.

## Descripción

El proyecto contiene dos apps independientes:

- **`magic.app/`**: lee mazos de Magic desde archivos `.txt` en la carpeta `decks/`, suma las cantidades del sideboard al main por mazo, y clasifica cada carta como **pauper / no-pauper** y por **tipo** (criatura, instantáneo/conjuro, planeswalker, artefacto, encantamiento, tierra) consultando la API de Scryfall. Tierras básicas se ignoran.
- **`pokemon.app/`**: scrapea decklists de Pokémon desde Limitless TCG (`play.limitlesstcg.com`), separa Pokémon de Trainers, y subclasifica los Trainers en **Supporter / Item / Tool / Stadium** consultando `limitlesstcg.com` (que expone el subtipo de cada carta). Energías básicas se ignoran.

## Apps disponibles

| Carpeta | Juego | Fuente |
|---|---|---|
| `magic.app/` | Magic: The Gathering | `decks/*.txt` + Scryfall |
| `pokemon.app/` | Pokemon TCG | `play.limitlesstcg.com` + `limitlesstcg.com` |

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

Dependencias principales: `requests`, `beautifulsoup4`.

## Uso

```bash
# Magic
cd magic.app && python scraper.py

# Pokémon
cd pokemon.app && python scraper.py
```

## Salida

### `magic.app`

Lee los mazos de la carpeta `decks/`, clasifica cada carta (pauper / no-pauper, y por tipo) consultando Scryfall con cache en `cards_db.json`, y compara con la **colección** del usuario (lo que ya tiene) para generar las **buylists** (lo que falta comprar).

**Archivos generados (salida):**
- `buylist_pauper.txt` — cartas pauper que faltan para playset de 4.
- `buylist_nopauper.txt` — cartas no-pauper que faltan hasta la cantidad del mazo.
- `export_unknown.txt` — cartas que Scryfall no pudo resolver (no van a buylist).

Formato: una línea por carta, `<cantidad> <nombre>`, ordenado alfabéticamente. Ejemplo:
```
2 Counterspell
4 Lightning Bolt
3 Murktide Regent
```

**Archivos de entrada que mantiene el usuario:**
- `decks/*.txt` — los mazos.
- `collection_pauper_*.txt` (6 archivos: `creatures`, `spells`, `planeswalkers`, `artifacts`, `enchantments`, `lands`) — cartas pauper que ya tienes, formato `<cantidad> <nombre>`.
- `collection_nopauper_*.txt` (6 archivos, mismos tipos) — cartas no-pauper que ya tienes, mismo formato.

**Cálculo de buylist por carta:**
- **Pauper** y **no-pauper**: `max(0, cantidad_en_mazo - cantidad_en_collection)`. La cantidad de la buylist es exactamente lo que falta para igualar la cantidad del mazo (main + sideboard). Si tienes 0 y el mazo pide 2, la buylist dice 2.
- Cartas en `collection` que no están en el mazo se ignoran.

**Modo interactivo:**

El script pregunta interactivamente por cada carta del mazo que **NO** está en `collection_*.txt` (cantidad 0). Las cartas que ya están en la colección con cualquier cantidad > 0 se procesan automáticamente sin preguntar.

Para cada carta no existente, el script muestra:
```
¿Tienes '<nombre>'? (Enter=no la tengo, número=cantidad):
```

- **Enter** (sin número): la carta no la tienes. Se agrega a la buylist con la cantidad completa del mazo.
- **Número + Enter**: tienes esa cantidad. Se actualiza el archivo `collection_*.txt` correspondiente en tiempo real. La carta no va a buylist (porque ahora tienes suficiente).

Las cartas ya presentes en la colección (cantidad > 0) se procesan automáticamente: se calcula `max(0, mazo - colección)` y la diferencia va a buylist. Si abortas la sesión con `Ctrl+C`, las cantidades respondidas hasta el momento quedan guardadas en los `collection_*.txt`.

**Prioridad de tipos** cuando una carta tiene varios (p.ej. *Artifact Creature*): Creature > Land > Planeswalker > Instant/Sorcery > Artifact > Enchantment.

**Cache local:** `cards_db.json` guarda `{nombre: {is_pauper, type_category}}` para evitar llamadas repetidas a Scryfall. Este archivo forma parte del repo (no se ignora en git) y nunca debe borrarse manualmente: se actualiza automáticamente al final de cada ejecución.

**Formato de los archivos de mazo:**

Coloca uno o varios archivos `.txt` en `magic.app/decks/`. Cada archivo representa un mazo y debe tener este formato:

```
4 Hearth Elemental
4 Sunderflock
...
6 Island

Sideboard
2 Annul
1 Broadside Barrage
...
```

- Una línea por carta: `<cantidad> <nombre>` (puede tener `x` opcional: `4x Lightning Bolt`).
- Las líneas vacías y las que empiezan por `#` o `//` se ignoran.
- Una sección opcional `Sideboard` (líneas que empiecen por `SB:` también se reconocen) cuyas cantidades se suman al main por carta.
- Las tierras básicas (`Plains`, `Island`, `Swamp`, `Mountain`, `Forest` y variantes `Snow-Covered`, `Wastes`) se ignoran automáticamente.

El script procesa **todos** los `.txt` de `decks/` y agrega las cartas tomando la cantidad máxima vista entre mazos.

### `pokemon.app`

Scrapea decklists de Limitless TCG (`play.limitlesstcg.com/.../decklist`), separa las cartas en Pokémon y Trainers, y subclasifica los Trainers en **Supporter / Item / Tool / Stadium** consultando `limitlesstcg.com` (que expone el subtipo de cada carta). Las energías básicas se ignoran.

**Archivos generados (salida):**
- `buylist_pokemon.txt` — cartas Pokémon que faltan hasta la cantidad del mazo.
- `buylist_trainers.txt` — Trainers (supporters, items, tools, stadiums, energies) que faltan para playset de 4.
- `export_unknown.txt` — Trainers cuyo subtipo no se pudo determinar (no van a buylist).

**Archivos de entrada que mantiene el usuario:**
- `urls.json` — URLs de los mazos a procesar.
- `collection_pokemon.txt` — cartas Pokémon que ya tienes, formato `<cantidad> <nombre>`.
- `collection_supporters.txt`, `collection_items.txt`, `collection_tools.txt`, `collection_stadiums.txt` — Trainers que ya tienes, mismo formato.
- `collection_energies.txt` — Energías no básicas que ya tienes.

**Cálculo de buylist por carta:**
- **Pokémon, Trainers (supporters / items / tools / stadiums) y Energies**: `max(0, cantidad_en_mazo - cantidad_en_collection)`. La cantidad de la buylist es exactamente lo que falta para igualar la cantidad del mazo. Si tienes 0 y el mazo pide 1, la buylist dice 1.
- Cartas en `collection` que no están en el mazo se ignoran.
- Cartas en `export_unknown.txt` no van a buylist (no se pueden clasificar).

**Modo interactivo:**

El script pregunta interactivamente por cada carta del mazo que **NO** está en `collection_*.txt` (cantidad 0). Las cartas que ya están en la colección con cualquier cantidad > 0 se procesan automáticamente sin preguntar.

Para cada carta no existente, el script muestra:
```
¿Tienes '<nombre>'? (Enter=no la tengo, número=cantidad):
```

- **Enter** (sin número): la carta no la tienes. Se agrega a la buylist con la cantidad completa del mazo.
- **Número + Enter**: tienes esa cantidad. Se actualiza el archivo `collection_*.txt` correspondiente en tiempo real. La carta no va a buylist (porque ahora tienes suficiente).

Las cartas ya presentes en la colección (cantidad > 0) se procesan automáticamente: se calcula `max(0, mazo - colección)` y la diferencia va a buylist. Si abortas la sesión con `Ctrl+C`, las cantidades respondidas hasta el momento quedan guardadas en los `collection_*.txt`.

**Cache local:** `cards_db.json` guarda `{nombre|set|numero: {supertype, subtype}}` para evitar llamadas repetidas a `limitlesstcg.com`. Este archivo forma parte del repo (no se ignora en git) y nunca debe borrarse manualmente.

**Configuración:** edita `urls.json` con las URLs de los mazos a procesar (formato: `https://play.limitlesstcg.com/tournament/.../player/.../decklist`).

**Uso:**
```bash
cd pokemon.app
# Editar urls.json con las URLs de play.limitlesstcg.com a procesar
# Rellenar los collection_*.txt con las cartas que ya tienes
python scraper.py
```

## Tech Stack

- [Python](https://www.python.org/) - Lenguaje de scripting.
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - Parseo de HTML.
- [Requests](https://requests.readthedocs.io/) - Peticiones HTTP.
- [Scryfall API](https://scryfall.com/docs/api) - Datos y legalidades de cartas de Magic.
- [Limitless TCG](https://limitlesstcg.com) - Decks y datos de cartas de Pokémon.
