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

                with open("exports/collection_pauper_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "4 Pauper Card\n")
                with open("exports/collection_non_pauper_spells.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "1 Non Pauper Card\n")
                self.assertFalse(os.path.exists("exports/collection_creatures.txt"))
                self.assertFalse(os.path.exists("exports/review_pauper_nonlegal.txt"))
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

                with open("exports/collection_pauper_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "4 Pauper Card\n")
                with open("exports/collection_non_pauper_spells.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "4 Non Pauper Card\n")
                self.assertFalse(os.path.exists("exports/deck_standard_alpha.txt"))
                self.assertFalse(os.path.exists("exports/deck_modern_beta.txt"))
                self.assertFalse(os.path.exists("exports/unknown.txt"))
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

                with open("exports/collection_pauper_creatures.txt", encoding="utf-8") as file:
                    self.assertEqual(file.read(), "1 alpha Card\n1 Zulu Card\n")
            finally:
                os.chdir(old_directory)

    def test_parse_card_line_and_basic_land_filter(self):
        self.assertEqual(scraper.parse_card_line("SB: 4x Lightning Bolt"), (4, "Lightning Bolt"))
        self.assertIsNone(scraper.parse_card_line("Sideboard"))
        self.assertIn("Island", scraper.BASIC_LANDS)

    def test_load_formats_preserves_order_and_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "decks.yaml")
            with open(path, "w", encoding="utf-8") as file:
                file.write(
                    "decks:\n"
                    "  standard:\n"
                    "    - https://example.test/standard\n"
                    "  modern: []\n"
                )

            formats = scraper.load_formats(path)

        self.assertEqual(
            formats,
            [("standard", ["https://example.test/standard"]), ("modern", [])],
        )

    def test_load_formats_fails_when_format_is_not_a_url_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "decks.yaml")
            with open(path, "w", encoding="utf-8") as file:
                file.write("decks:\n  standard:\n    deck: invalid\n")

            with self.assertRaisesRegex(ValueError, "lista de URLs"):
                scraper.load_formats(path)

    def test_parses_mtgdecks_arena_deck_with_sideboard(self):
        content = b"""
        <html><body><textarea id="arena_deck">
        Deck
        4 Main Card
        2 Forest
        Sideboard
        1 Side Card
        </textarea></body></html>
        """

        self.assertEqual(
            scraper.parse_deck_response(content),
            [[4, "Main Card"], [1, "Side Card"]],
        )

    def test_extracts_deck_name_from_mtgdecks_url(self):
        url = "https://mtgdecks.net/Standard/izzet-spellementals-decklist-by-brunninho-3152160"

        self.assertEqual(scraper.deck_name_from_url(url), "izzet spellementals")


if __name__ == "__main__":
    unittest.main()
