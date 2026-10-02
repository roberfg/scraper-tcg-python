import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "pokemon.app",
    "scraper.py",
)
SPEC = importlib.util.spec_from_file_location("pokemon_scraper", MODULE_PATH)
scraper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scraper)


class PokemonScraperTests(unittest.TestCase):
    def test_standard_uses_maximum_quantity(self):
        decks = [
            {
                "Pokemon": [["Pikachu", "SVI", "062", 2]],
                "Trainer": [],
                "Energy": [],
            },
            {
                "Pokemon": [["Pikachu", "SVI", "062", 4]],
                "Trainer": [],
                "Energy": [],
            },
        ]

        aggregated = scraper.aggregate_cards(decks, glc=False)

        self.assertEqual(aggregated["Pokemon"], [["Pikachu", "SVI", "062", 4]])

    def test_glc_forces_quantity_one(self):
        decks = [
            {
                "Pokemon": [["Pikachu", "SVI", "062", 4]],
                "Trainer": [],
                "Energy": [],
            },
            {
                "Pokemon": [["Pikachu", "SVI", "062", 2]],
                "Trainer": [],
                "Energy": [],
            },
        ]

        aggregated = scraper.aggregate_cards(decks, glc=True)

        self.assertEqual(aggregated["Pokemon"], [["Pikachu", "SVI", "062", 1]])

    def test_process_format_writes_format_specific_files(self):
        decks = [{
            "Pokemon": [["Pikachu", "SVI", "062", 4]],
            "Trainer": [["Nest Ball", "SVI", "181", 4]],
            "Energy": [["Double Turbo Energy", "BRS", "151", 2]],
        }]

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                scraper,
                "fetch_card_subtype",
                return_value=({"supertype": "Trainer", "subtype": "Item"}, True),
            ):
                scraper.process_format("standard", decks, {}, directory)

            with open(os.path.join(directory, "collection_standard_pokemon.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "4 Pikachu (SVI-062)\n")
            with open(os.path.join(directory, "collection_standard_items.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "4 Nest Ball\n")
            with open(os.path.join(directory, "collection_standard_energies.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "2 Double Turbo Energy\n")

    def test_process_format_sorts_collection_cards_alphabetically(self):
        decks = [{
            "Pokemon": [
                ["Zacian", "SWSH", "001", 1],
                ["Abra", "SVI", "002", 2],
            ],
            "Trainer": [
                ["Ultra Ball", "SVI", "003", 1],
                ["Boss's Orders", "SVI", "004", 2],
            ],
            "Energy": [
                ["Water Energy", "SVE", "003", 1],
                ["Double Turbo Energy", "BRS", "151", 2],
            ],
        }]

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                scraper,
                "fetch_card_subtype",
                side_effect=[
                    ({"supertype": "Trainer", "subtype": "Item"}, True),
                    ({"supertype": "Trainer", "subtype": "Item"}, True),
                ],
            ):
                scraper.process_format("standard", decks, {}, directory)

            with open(os.path.join(directory, "collection_standard_pokemon.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "2 Abra (SVI-002)\n1 Zacian (SWSH-001)\n")
            with open(os.path.join(directory, "collection_standard_items.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "2 Boss's Orders\n1 Ultra Ball\n")
            with open(os.path.join(directory, "collection_standard_energies.txt"), encoding="utf-8") as file:
                self.assertEqual(file.read(), "2 Double Turbo Energy\n1 Water Energy\n")

    def test_load_formats_preserves_format_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "decks.yaml")
            with open(path, "w", encoding="utf-8") as file:
                file.write(
                    "decks:\n"
                    "  standard:\n"
                    "    - url-standard\n"
                    "  glc:\n"
                    "    - url-glc\n"
                )

            formats = scraper.load_formats(path)

        self.assertEqual(formats, [("standard", ["url-standard"]), ("glc", ["url-glc"])])

if __name__ == "__main__":
    unittest.main()
