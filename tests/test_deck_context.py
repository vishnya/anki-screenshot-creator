import pytest
from unittest.mock import patch

import flask_server
import models


class TestFetchDeckCards:
    """fetch_deck_cards retrieves and formats cards from AnkiConnect."""

    def test_returns_formatted_cards(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1, 2, 3]
            if action == "notesInfo":
                return [
                    {"fields": {"Front": {"value": "What is X?"}, "Back": {"value": "X is Y."}}, "tags": ["bio"]},
                    {"fields": {"Front": {"value": "Why Z?"}, "Back": {"value": "Because W."}}, "tags": ["bio", "ch1"]},
                    {"fields": {"Front": {"value": "Define Q"}, "Back": {"value": "Q means R."}}, "tags": []},
                ]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert len(cards) == 3
        assert cards[0] == {"front": "What is X?", "back": "X is Y.", "tags": ["bio"]}
        assert cards[1]["tags"] == ["bio", "ch1"]

    def test_limits_to_most_recent(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return list(range(100))
            if action == "notesInfo":
                # Should only receive the last 30 IDs
                assert len(params["notes"]) == 30
                assert params["notes"] == list(range(70, 100))
                return [
                    {"fields": {"Front": {"value": f"Q{i}"}, "Back": {"value": f"A{i}"}}, "tags": []}
                    for i in params["notes"]
                ]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck", limit=30)

        assert len(cards) == 30

    def test_strips_html_from_backs(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [{"fields": {
                    "Front": {"value": "Q?"},
                    "Back": {"value": 'Answer text<br><img src="screenshot.png">'},
                }, "tags": []}]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert cards[0]["back"] == "Answer text"

    def test_strips_html_from_fronts(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [{"fields": {
                    "Front": {"value": "<b>Bold question?</b>"},
                    "Back": {"value": "Answer"},
                }, "tags": []}]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert cards[0]["front"] == "Bold question?"

    def test_truncates_long_backs(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [{"fields": {
                    "Front": {"value": "Q?"},
                    "Back": {"value": "A" * 500},
                }, "tags": []}]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert len(cards[0]["back"]) == 200

    def test_empty_deck_returns_empty(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return []

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert cards == []

    def test_error_returns_empty(self):
        with patch("flask_server._ankiconnect", side_effect=Exception("Anki not running")):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert cards == []

    def test_skips_cards_with_empty_front(self):
        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1, 2]
            if action == "notesInfo":
                return [
                    {"fields": {"Front": {"value": ""}, "Back": {"value": "orphan"}}, "tags": []},
                    {"fields": {"Front": {"value": "Q?"}, "Back": {"value": "A."}}, "tags": []},
                ]

        with patch("flask_server._ankiconnect", side_effect=ankiconnect):
            cards = flask_server.fetch_deck_cards("TestDeck")

        assert len(cards) == 1
        assert cards[0]["front"] == "Q?"


class TestFormatDeckContext:
    """_format_deck_context builds the prompt section."""

    def test_empty_returns_empty_string(self):
        assert models._format_deck_context([]) == ""

    def test_formats_cards_with_tags(self):
        cards = [
            {"front": "What is X?", "back": "X is Y.", "tags": ["bio", "ch1"]},
            {"front": "Why Z?", "back": "Because W.", "tags": []},
        ]
        result = models._format_deck_context(cards)
        assert 'Q: "What is X?" / A: "X is Y."  [bio, ch1]' in result
        assert 'Q: "Why Z?" / A: "Because W."' in result
        assert "NEVER create a card that tests the same fact" in result

    def test_no_tag_bracket_when_empty(self):
        cards = [{"front": "Q?", "back": "A.", "tags": []}]
        result = models._format_deck_context(cards)
        assert "[" not in result.split("\n")[1]  # the card line itself


class TestBuildPromptWithContext:
    """_build_prompt integrates deck context into the prompt."""

    def test_no_context_returns_base(self):
        prompt = models._build_prompt({"deck_context": []})
        assert "EXISTING CARDS" not in prompt
        assert "RULES:" in prompt

    def test_context_appears_before_rules(self):
        config = {"deck_context": [
            {"front": "What is DNA?", "back": "A molecule.", "tags": ["bio"]},
        ]}
        prompt = models._build_prompt(config)
        assert "EXISTING CARDS IN THIS DECK" in prompt
        assert 'Q: "What is DNA?"' in prompt
        # Context should appear before RULES
        ctx_pos = prompt.index("EXISTING CARDS")
        rules_pos = prompt.index("RULES:")
        assert ctx_pos < rules_pos

    def test_context_with_custom_prompt(self):
        config = {
            "deck_context": [{"front": "Q?", "back": "A.", "tags": []}],
            "custom_prompt": "Write in Spanish",
        }
        prompt = models._build_prompt(config)
        assert "EXISTING CARDS" in prompt
        assert "Write in Spanish" in prompt
        assert "RULES:" in prompt

    def test_context_and_custom_prompt_ordering(self):
        """Custom prompt should appear before RULES, deck context before that."""
        config = {
            "deck_context": [{"front": "Q?", "back": "A.", "tags": []}],
            "custom_prompt": "Focus on clinical applications",
        }
        prompt = models._build_prompt(config)
        ctx_pos = prompt.index("EXISTING CARDS")
        user_pos = prompt.index("USER INSTRUCTION")
        rules_pos = prompt.index("RULES:")
        assert ctx_pos < user_pos < rules_pos


class TestDeckContextIntegration:
    """End-to-end: screenshot processing fetches deck context."""

    def test_on_created_passes_deck_context(self, tmp_config, tiny_png):
        from unittest.mock import MagicMock
        handler = flask_server.ScreenshotHandler()
        event = MagicMock()
        event.src_path = tiny_png
        event.is_directory = False

        conf = dict(tmp_config)
        conf["session_active"] = True
        conf["deck"] = "TestDeck"

        captured_config = []
        def mock_generate(path, config):
            captured_config.append(config)
            return [{"front": "Q", "back": "A", "tags": [], "is_image_card": False}]

        existing_cards = [
            {"front": "Old Q?", "back": "Old A.", "tags": ["bio"]},
        ]

        def ankiconnect(action, **params):
            if action == "findNotes":
                return [1]
            if action == "notesInfo":
                return [{"fields": {
                    "Front": {"value": "Old Q?"},
                    "Back": {"value": "Old A."},
                }, "tags": ["bio"]}]
            if action == "deckNames":
                return ["TestDeck"]
            if action == "addNote":
                return 12345

        with patch("flask_server.cfg.load", return_value=conf), \
             patch("flask_server.models.generate_cards", side_effect=mock_generate), \
             patch("flask_server._ankiconnect", side_effect=ankiconnect), \
             patch("flask_server._push_event"), \
             patch("time.sleep"):
            handler.on_created(event)

        assert len(captured_config) == 1
        assert "deck_context" in captured_config[0]
        assert len(captured_config[0]["deck_context"]) == 1
        assert captured_config[0]["deck_context"][0]["front"] == "Old Q?"
