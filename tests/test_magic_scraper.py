import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "magic.app",
    "scraper.py",
)
SPEC = importlib.util.spec_from_file_location("magic_scraper", MODULE_PATH)
scraper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scraper)


class MagicScraperTests(unittest.TestCase):
    def test_moves_non_pauper_cards_from_pauper_decks_to_review_file(self):
        decks = [
            {"format": "pauper", "name": "Tron", "path": "tron.txt"},
        ]
        card_info = {
            "Pauper Card": {"is_pauper": True, "type_category": "creatures"},
            "Non Pauper Card": {"is_pauper": False, "type_category": "spells"},
        }

        with tempfile.TemporaryDirectory() as directory:
            old_directory = os.getcwd()
            os.chdir(directory)
            try:
                with open("tron.txt", "w", encoding="utf-8") as file:
                    file.write("4 Pauper Card\n1 Non Pauper Card\n")

                with patch.object(
                    scraper,
                    "fetch_card_info",
                    side_effect=lambda name, cards_db: (card_info.get(name), True),
                ):
                    scraper.process_decks(decks, {})

                with open("exports/collection_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "4 Pauper Card\n")
                with open("exports/review_pauper_nonlegal.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "1 Non Pauper Card (deck_pauper_tron)\n")
                self.assertFalse(os.path.exists("exports/deck_pauper_tron.txt"))
            finally:
                os.chdir(old_directory)

    def test_processes_local_decks_in_yaml_order(self):
        decks = [
            {"format": "standard", "name": "Alpha", "path": "alpha.txt"},
            {"format": "modern", "name": "Beta", "path": "beta.txt"},
        ]
        card_info = {
            "Pauper Card": {"is_pauper": True, "type_category": "creatures"},
            "Non Pauper Card": {"is_pauper": False, "type_category": "spells"},
        }

        with tempfile.TemporaryDirectory() as directory:
            old_directory = os.getcwd()
            os.chdir(directory)
            try:
                with open("alpha.txt", "w", encoding="utf-8") as file:
                    file.write("4 Pauper Card\n2 Non Pauper Card\n\n1 Unknown Card\n")
                with open("beta.txt", "w", encoding="utf-8") as file:
                    file.write("3 Pauper Card\n4 Non Pauper Card\n1 Unknown Card\n")

                with patch.object(
                    scraper,
                    "fetch_card_info",
                    side_effect=lambda name, cards_db: (card_info.get(name), True),
                ):
                    scraper.process_decks(decks, {})

                with open("exports/collection_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "4 Pauper Card\n")
                with open("exports/deck_standard_alpha.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "2 Non Pauper Card\n")
                with open("exports/deck_modern_beta.txt", encoding="utf-8") as file:
                    self.assertEqual(
                        file.read(),
                        "4 Non Pauper Card (2 en deck_standard_alpha)\n",
                    )
                with open("exports/unknown.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "Unknown Card\n")
            finally:
                os.chdir(old_directory)

    def test_sorts_collection_cards_alphabetically_without_sorting_decks(self):
        decks = [{"format": "standard", "name": "Alpha", "path": "alpha.txt"}]
        card_info = {
            "Zulu Card": {"is_pauper": True, "type_category": "creatures"},
            "alpha Card": {"is_pauper": True, "type_category": "creatures"},
        }

        with tempfile.TemporaryDirectory() as directory:
            old_directory = os.getcwd()
            os.chdir(directory)
            try:
                with open("alpha.txt", "w", encoding="utf-8") as file:
                    file.write("1 Zulu Card\n1 alpha Card\n")

                with patch.object(
                    scraper,
                    "fetch_card_info",
                    side_effect=lambda name, cards_db: (card_info[name], True),
                ):
                    scraper.process_decks(decks, {})

                with open("exports/collection_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "1 alpha Card\n1 Zulu Card\n")
            finally:
                os.chdir(old_directory)

    def test_parse_card_line_and_basic_land_filter(self):
        self.assertEqual(scraper.parse_card_line("SB: 4x Lightning Bolt"), (4, "Lightning Bolt"))
        self.assertIsNone(scraper.parse_card_line("Sideboard"))
        self.assertIn("Island", scraper.BASIC_LANDS)

    def test_load_decks_resolves_txt_files_and_preserves_order(self):
        with tempfile.TemporaryDirectory() as directory:
            decks_dir = os.path.join(directory, "decks")
            os.makedirs(decks_dir)
            with open(os.path.join(decks_dir, "First Deck.txt"), "w", encoding="utf-8") as file:
                file.write("1 Card\n")
            with open(os.path.join(decks_dir, "Second Deck (1).txt"), "w", encoding="utf-8") as file:
                file.write("1 Card\n")
            path = os.path.join(decks_dir, "decks.yaml")
            with open(path, "w", encoding="utf-8") as file:
                file.write(
                    "decks:\n"
                    "  standard:\n"
                    "    first deck: First Deck\n"
                    "  modern:\n"
                    "    second deck: Second Deck (1)\n"
                )

            decks = scraper.load_decks(path)

        self.assertEqual(
            [(deck["format"], deck["name"]) for deck in decks],
            [("standard", "first deck"), ("modern", "second deck")],
        )
        self.assertTrue(decks[0]["path"].endswith("First Deck.txt"))

    def test_load_decks_fails_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "decks.yaml")
            with open(path, "w", encoding="utf-8") as file:
                file.write("decks:\n  standard:\n    missing: Does Not Exist\n")

            with self.assertRaisesRegex(FileNotFoundError, "missing.*standard"):
                scraper.load_decks(path)


if __name__ == "__main__":
    unittest.main()
