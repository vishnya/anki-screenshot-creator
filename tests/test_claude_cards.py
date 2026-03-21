"""
Tests for claude_cards.py, claude_cards_queue.py, and claude_cards_sync.py.
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import claude_cards
import claude_cards_queue


class TestCreateCards:
    """Test bidirectional card creation."""

    def _mock_ankiconnect(self, calls):
        def mock(action, **params):
            calls.append((action, params))
            if action == "deckNames":
                return ["Claude System Design Learnings"]
            if action == "addNote":
                return 12345
            return None
        return mock

    def test_creates_two_cards(self):
        calls = []
        with patch.object(claude_cards, "ankiconnect", self._mock_ankiconnect(calls)):
            created = claude_cards.create_cards(
                "test concept", "test def", "test scenario", "test example",
                "Claude System Design Learnings",
            )
        assert created == 2
        add_calls = [c for c in calls if c[0] == "addNote"]
        assert len(add_calls) == 2

    def test_recall_card_has_scenario_on_front(self):
        """Card 1 front should be the scenario (no concept name)."""
        calls = []
        with patch.object(claude_cards, "ankiconnect", self._mock_ankiconnect(calls)):
            claude_cards.create_cards(
                "ring buffer", "a fixed-size list",
                "A server needs to keep recent events for reconnecting clients without unlimited memory. How?",
                "Walkie uses a 500-event buffer.",
                "Claude System Design Learnings",
            )
        add_calls = [c for c in calls if c[0] == "addNote"]
        card1_front = add_calls[0][1]["note"]["fields"]["Front"]
        card1_back = add_calls[0][1]["note"]["fields"]["Back"]
        # Front should NOT contain the concept name
        assert "ring buffer" not in card1_front
        # Front should contain the scenario
        assert "reconnecting clients" in card1_front
        # Back should contain the concept name
        assert "ring buffer" in card1_back
        assert "a fixed-size list" in card1_back

    def test_define_card_has_concept_on_front(self):
        """Card 2 front should name the concept."""
        calls = []
        with patch.object(claude_cards, "ankiconnect", self._mock_ankiconnect(calls)):
            claude_cards.create_cards(
                "ring buffer", "a fixed-size list",
                "scenario here", "example here",
                "Claude System Design Learnings",
            )
        add_calls = [c for c in calls if c[0] == "addNote"]
        card2_front = add_calls[1][1]["note"]["fields"]["Front"]
        card2_back = add_calls[1][1]["note"]["fields"]["Back"]
        assert "ring buffer" in card2_front
        assert "a fixed-size list" in card2_back
        assert "example here" in card2_back

    def test_both_cards_have_example_on_back(self):
        """Both cards should include the real example on the back."""
        calls = []
        with patch.object(claude_cards, "ankiconnect", self._mock_ankiconnect(calls)):
            claude_cards.create_cards(
                "concept", "def", "scenario", "Walkie did this thing",
                "Claude System Design Learnings",
            )
        add_calls = [c for c in calls if c[0] == "addNote"]
        for call in add_calls:
            assert "Walkie did this thing" in call[1]["note"]["fields"]["Back"]

    def test_creates_deck_if_missing(self):
        calls = []
        def mock(action, **params):
            calls.append((action, params))
            if action == "deckNames":
                return ["Default"]
            if action == "createDeck":
                return None
            if action == "addNote":
                return 12345
            return None

        with patch.object(claude_cards, "ankiconnect", mock):
            claude_cards.create_cards("t", "d", "s", "e", "New Deck")

        create_calls = [c for c in calls if c[0] == "createDeck"]
        assert len(create_calls) == 1
        assert create_calls[0][1]["deck"] == "New Deck"

    def test_skips_duplicates(self):
        call_count = 0
        def mock(action, **params):
            nonlocal call_count
            if action == "deckNames":
                return ["Claude System Design Learnings"]
            if action == "addNote":
                call_count += 1
                if call_count == 1:
                    raise Exception("cannot create note because it is a duplicate")
                return 12345
            return None

        with patch.object(claude_cards, "ankiconnect", mock):
            created = claude_cards.create_cards("t", "d", "s", "e", "Claude System Design Learnings")
        assert created == 1

    def test_tags_include_claude_session(self):
        calls = []
        with patch.object(claude_cards, "ankiconnect", self._mock_ankiconnect(calls)):
            claude_cards.create_cards("t", "d", "s", "e", "Claude System Design Learnings")
        add_calls = [c for c in calls if c[0] == "addNote"]
        for call in add_calls:
            assert "claude-session" in call[1]["note"]["tags"]


class TestCardQueue:
    """Test the queue flow for server sessions."""

    def test_queue_creates_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            queue_file = f.name
            f.write(b"[]")

        try:
            with patch.object(claude_cards_queue, "QUEUE_FILE", queue_file):
                claude_cards_queue.queue_card("concept", "def", "scenario", "example", "Deck")

            with open(queue_file) as f:
                queue = json.load(f)

            assert len(queue) == 1
            assert queue[0]["concept"] == "concept"
            assert queue[0]["scenario"] == "scenario"
            assert queue[0]["example"] == "example"
        finally:
            os.unlink(queue_file)

    def test_queue_appends(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            queue_file = f.name
            f.write(b"[]")

        try:
            with patch.object(claude_cards_queue, "QUEUE_FILE", queue_file):
                claude_cards_queue.queue_card("c1", "d1", "s1", "e1", "Deck")
                claude_cards_queue.queue_card("c2", "d2", "s2", "e2", "Deck")

            with open(queue_file) as f:
                queue = json.load(f)
            assert len(queue) == 2
        finally:
            os.unlink(queue_file)

    def test_queue_handles_missing_file(self):
        queue_file = tempfile.mktemp(suffix=".json")
        try:
            with patch.object(claude_cards_queue, "QUEUE_FILE", queue_file):
                claude_cards_queue.queue_card("new", "def", "scen", "ex", "Deck")
            assert os.path.exists(queue_file)
            with open(queue_file) as f:
                assert len(json.load(f)) == 1
        finally:
            if os.path.exists(queue_file):
                os.unlink(queue_file)

    def test_load_empty_queue(self):
        with patch.object(claude_cards_queue, "QUEUE_FILE", "/nonexistent/path.json"):
            assert claude_cards_queue.load_queue() == []
