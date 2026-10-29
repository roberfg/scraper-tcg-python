# Contexto del Proyecto

## Propósito

Este repositorio contiene dos scrapers independientes para mantener colecciones de cartas:

- `magic.app/`: Magic: The Gathering.
- `pokemon.app/`: Pokémon TCG.

Las explicaciones y la documentación del proyecto están en español. Los identificadores y el código permanecen en inglés.

## Estructura

```text
scraper-tcg-python/
├── magic.app/
│   ├── scraper.py
│   ├── decks/
│   │   ├── decks.yaml
│   │   └── decks.yaml.example
│   ├── cards_db.json
│   ├── decks_cache.json
│   └── exports/
├── pokemon.app/
│   ├── scraper.py
│   ├── decks/decks.yaml
│   ├── cards_db.json
│   ├── decks_cache.json
│   └── export/
├── tests/
│   ├── test_magic_scraper.py
│   └── test_pokemon_scraper.py
├── requirements.txt
└── README.md
```

Los archivos de configuración, caché, bases de datos y salidas son locales y están ignorados por Git. Las plantillas `.example` sí están versionadas.

## Magic

### Fuente

Los mazos se descargan desde páginas individuales de `mtgdecks.net`. La lista se encuentra en el elemento HTML `#arena_deck` y contiene maindeck y sideboard.

El scraper usa `curl/8.0` como `User-Agent` porque `mtgdecks.net` puede devolver contenido distinto o un `403` según el identificador del cliente. No cambiarlo sin volver a validar el deck recibido.

### Configuración actual

Archivo: `magic.app/decks/decks.yaml`.

```yaml
decks:
  pauper: []
  standard:
    - https://mtgdecks.net/Standard/izzet-spellementals-decklist-by-brunninho-3152160
  modern: []
  premodern: []
  pioneer: []
```

Cada formato contiene una lista de URLs. Para agregar mazos, se añade una URL al formato correspondiente. El formato correcto es `premodern`, no `premoder`.

### Flujo de Magic

1. Carga las URLs de `decks/decks.yaml`.
2. Descarga cada deck o lo obtiene desde `decks_cache.json`.
3. Extrae las líneas de `#arena_deck`.
4. Incluye el sideboard.
5. Ignora tierras básicas.
6. Consulta Scryfall para determinar legalidad Pauper y tipo de carta.
7. Agrupa las cartas por legalidad y tipo.
8. Regenera completamente `magic.app/exports/`.

Las categorías de tipo son:

- `creatures`
- `lands`
- `planeswalkers`
- `spells`
- `artifacts`
- `enchantments`

La prioridad cuando una carta tiene varios tipos es: Creature, Land, Planeswalker, Instant/Sorcery, Artifact, Enchantment.

### Salidas de Magic

La salida permitida está limitada a estos patrones:

```text
collection_pauper_<tipo>.txt
collection_non_pauper_<tipo>.txt
```

Se generan ambos archivos para cada categoría, incluso si uno queda vacío. No se deben generar:

- `collection_<tipo>.txt`.
- `deck_<formato>_<mazo>.txt`.
- `unknown.txt`.
- `review_pauper_nonlegal.txt`.

Las cartas repetidas entre mazos conservan la cantidad máxima. Las cartas desconocidas se informan en consola, pero no se escriben en un archivo adicional.

### Caché y ejecución

Desde `magic.app/`:

```bash
python scraper.py
python scraper.py --refresh
```

`--refresh` ignora la caché de mazos y vuelve a descargar las URLs. La caché de cartas de Scryfall se conserva en `cards_db.json`.

## Pokémon

`pokemon.app/scraper.py` mantiene un flujo separado. Usa URLs de `play.limitlesstcg.com`, clasifica Pokémon y Trainers y genera colecciones por formato y subtipo. No mezclar la configuración ni la caché de Pokémon con las de Magic.

Desde `pokemon.app/`:

```bash
python scraper.py
python scraper.py --refresh
```

## Pruebas

No asumir que `pytest` está instalado. La suite se puede ejecutar con la librería estándar:

```bash
python -m unittest discover -s tests
```

También se puede validar la sintaxis de Magic con:

```bash
python -m py_compile magic.app/scraper.py
```

## Reglas de mantenimiento

- No crear archivos de salida adicionales para Magic sin actualizar este contexto y el README.
- No cambiar el selector `#arena_deck` sin probar una URL real.
- Si una URL devuelve un mazo inesperado, ejecutar `python scraper.py --refresh` y revisar el `User-Agent` antes de aceptar la caché.
- Mantener la caché local fuera de Git.
- Ejecutar la suite de tests después de cambiar el formato YAML o la clasificación de cartas.
