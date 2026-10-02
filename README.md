# tcg-scraper-python

Scripts para actualizar colecciones de cartas de Magic: The Gathering y Pokémon TCG a partir de listas de mazos.

## Descripción

El proyecto contiene dos apps independientes:

- **`magic.app/`**: lee mazos de Magic desde `decks/decks.yaml` y archivos locales `.txt`, clasifica cada carta por **legalidad Pauper** y **tipo** (criatura, instantáneo/conjuro, planeswalker, artefacto, encantamiento, tierra) consultando la API de Scryfall y genera las salidas en `exports/`. Tierras básicas se ignoran.
- **`pokemon.app/`**: scrapea listas de Pokémon desde `decks/decks.yaml`, separa Pokémon de Trainers y subclasifica los Trainers en **Supporter / Item / Tool / Stadium** consultando `limitlesstcg.com`. Energías básicas se ignoran.

Los archivos locales de datos, configuración, caché y salida están ignorados por Git. Las plantillas versionadas terminan en `.example`; para usarlas, copia cada plantilla y elimina ese sufijo.

## Apps disponibles

| Carpeta | Juego | Fuente |
|---|---|---|
| `magic.app/` | Magic: The Gathering | Listas locales + Scryfall |
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

Dependencias principales: `requests`, `beautifulsoup4`, `PyYAML`.

## Uso

```bash
# Magic
(cd magic.app && python scraper.py)

# Pokémon
(cd pokemon.app && python scraper.py)
```

## Salida

### `magic.app`

Lee `decks/decks.yaml`, procesa las listas locales de `decks/*.txt` y clasifica las cartas por legalidad Pauper y tipo consultando Scryfall.

La salida se regenera directamente en `exports/`:

```text
magic.app/
├── decks/
│   ├── decks.yaml.example
│   ├── Deck - Example.txt.example
│   └── Deck - Nombre del mazo.txt
├── cards_db.json.example
└── exports/
    ├── collection_artifacts.txt
    ├── collection_creatures.txt
    ├── collection_enchantments.txt
    ├── collection_lands.txt
    ├── collection_planeswalkers.txt
    ├── collection_spells.txt
    ├── deck_modern_izzet_prowess.txt
    ├── review_pauper_nonlegal.txt
    └── unknown.txt
```

- `collection_<tipo>.txt` contiene las cartas Pauper agrupadas por tipo. Si una carta aparece en varios mazos, se conserva la cantidad máxima.
- `deck_<formato>_<mazo>.txt` contiene las cartas no Pauper de cada mazo, en el orden original.
- Los mazos con formato `pauper` no generan archivos `deck_pauper_*.txt`; sus cartas legales se consolidan en las colecciones.
- `review_pauper_nonlegal.txt` contiene las cartas clasificadas como no Pauper que aparecen dentro de mazos Pauper, junto con el deck de origen, para revisión manual.
- Las cartas no Pauper que ya aparecieron en un mazo anterior incluyen una referencia a su primera aparición, por ejemplo `4 Arid Mesa (4 en deck_standard_boros_algo)`.
- `unknown.txt` contiene una sola vez cada carta que Scryfall no pudo resolver o clasificar.
- Todos los archivos `.txt` anteriores de `exports/` se eliminan y regeneran en cada ejecución.

La ejecución muestra trazas detalladas con prefijos `[Magic]`, `[Scryfall]`, `[Pokemon]` y `[Limitless]`, incluyendo el uso de caché, las cartas procesadas, su clasificación y los archivos generados.

**Formato de `decks/decks.yaml`:**

```yaml
decks:
  standard:
    izzet spellelementals: Deck - Izzet Spellementals
  modern:
    izzet prowess: Deck - Izzet Prowess
  pioneer:
    izzet prowess: Deck - Izzet Prowess (1)
  pauper:
    mono red madness: Deck - Mono Red Madness
```

Cada valor se resuelve como un archivo `.txt` dentro de la misma carpeta `decks/`. No se escribe la extensión en el YAML. El orden de formatos y mazos se conserva al procesar las referencias entre mazos.

Si falta un archivo referenciado, el proceso se detiene y muestra el formato, el nombre del mazo y la ruta faltante. Los archivos de `exports/` se limpian únicamente después de validar y leer todos los mazos.

Las tierras básicas se ignoran. Las cartas del sideboard se incluyen, incluyendo líneas con prefijo `SB:`.

La prioridad de tipos cuando una carta tiene varios es: Creature > Land > Planeswalker > Instant/Sorcery > Artifact > Enchantment.

**Formato de cada lista local:**

Cada mazo debe devolver líneas con este formato:

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
- Una sección opcional `Sideboard` (líneas que empiecen por `SB:` también se reconocen) cuyas cartas también se procesan.
- Las tierras básicas (`Plains`, `Island`, `Swamp`, `Mountain`, `Forest` y variantes `Snow-Covered`, `Wastes`) se ignoran automáticamente.

El script procesa los mazos en el orden del YAML y agrega las cartas Pauper tomando la cantidad máxima vista entre mazos.

### `pokemon.app`

Scrapea listas de Limitless TCG (`play.limitlesstcg.com/.../decklist`), separa las cartas en Pokémon y Trainers, y subclasifica los Trainers en **Supporter / Item / Tool / Stadium** consultando `limitlesstcg.com`. Las energías básicas se ignoran.

**Estructura y archivos actualizados:**

```text
pokemon.app/
├── decks/
│   └── decks.yaml.example
├── cards_db.json.example
├── decks_cache.json.example
└── export/
    ├── collection_standard_pokemon.txt
    ├── collection_standard_items.txt
    ├── collection_standard_supporters.txt
    ├── collection_standard_tools.txt
    ├── collection_standard_stadiums.txt
    ├── collection_standard_energies.txt
    ├── collection_glc_pokemon.txt
    ├── collection_glc_items.txt
    ├── collection_glc_supporters.txt
    ├── collection_glc_tools.txt
    ├── collection_glc_stadiums.txt
    ├── collection_glc_energies.txt
    ├── unknown_standard.txt
    └── unknown_glc.txt
```

- Cada archivo `collection_<formato>_<tipo>.txt` contiene todas las cartas de ese formato agregadas desde sus listas.
- En `standard` se conserva la cantidad máxima de cada carta.
- En `glc` todas las cartas se escriben con cantidad `1`.
- Las cartas Pokémon conservan su impresión, por ejemplo `4 Pikachu (SVI-062)`.
- `unknown_<formato>.txt` contiene Trainers cuyo subtipo no se pudo determinar.
- `decks_cache.json` conserva las listas descargadas por URL para evitar consultas repetidas.

El script regenera directamente los archivos `.txt` de `export/` en cada ejecución.

**Formato de `decks/decks.yaml`:**

```yaml
decks:
  standard:
    - https://play.limitlesstcg.com/tournament/.../player/.../decklist
  glc:
    - https://play.limitlesstcg.com/tournament/.../player/.../decklist
```

Los valores son únicamente URLs y no tienen nombre de mazo. El orden de los formatos se conserva. Si una URL aparece varias veces dentro de un formato, la cache evita descargarla más de una vez.

**Salida en consola:**

Las salidas contienen las cartas completas de cada formato, no diferencias contra una colección existente.

**Caché local:** `cards_db.json` guarda `{nombre|set|numero: {supertype, subtype}}` para evitar llamadas repetidas a `limitlesstcg.com`. Se genera y conserva localmente; no se versiona ni debe borrarse manualmente.

**Configuración:** copia `decks/decks.yaml.example` como `decks/decks.yaml` y edítalo con las URLs de los mazos a procesar.

Si una URL ya está en `decks_cache.json`, no se vuelve a consultar. Para forzar la actualización de todos los mazos usa `python scraper.py --refresh`. Esta opción vuelve a descargar las decklists y actualiza `decks_cache.json`; no borra las colecciones ni fuerza la actualización de las cartas que ya están en `cards_db.json`.

**Uso:**
```bash
cd pokemon.app
# Editar decks/decks.yaml con las URLs de Limitless TCG
python scraper.py
```

## Tech Stack

- [Python](https://www.python.org/) - Lenguaje de scripting.
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - Parseo de HTML.
- [Requests](https://requests.readthedocs.io/) - Peticiones HTTP.
- [Scryfall API](https://scryfall.com/docs/api) - Datos y legalidades de cartas de Magic.
- [Limitless TCG](https://limitlesstcg.com) - Decks y datos de cartas de Pokémon.
