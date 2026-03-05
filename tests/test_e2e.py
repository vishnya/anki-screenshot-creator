import pytest
from unittest.mock import MagicMock, patch

import flask_server
from flask_server import ScreenshotHandler


def make_event(path):
    event = MagicMock()
    event.src_path = path
    event.is_directory = False
    return event


def test_full_screenshot_pipeline(flask_client, tmp_config, tiny_png, mock_ankiconnect):
    # 1. Set deck
    flask_client.post("/api/config", json={"deck": "TestDeck"})
    # 2. Start session
    flask_client.post("/api/session/start")

    # 3. Mock generate_cards
    fake_cards = [
        {"front": "Q1", "back": "A1", "tags": [], "is_image_card": False},
        {"front": "Q2", "back": "A2", "tags": [], "is_image_card": False},
    ]

    # 4. Trigger on_created (mock_ankiconnect fixture is already active)
    handler = ScreenshotHandler()
    event = make_event(tiny_png)

    with patch("flask_server.models.generate_cards", return_value=fake_cards), \
         patch("time.sleep"):
        handler.on_created(event)

    # 5. Verify addNote was called twice
    add_note_calls = [
        c for c in mock_ankiconnect.call_args_list if c[0][0] == "addNote"
    ]
    assert len(add_note_calls) == 2

    # 6. Verify _recent_cards has 2 entries
    assert len(flask_server._recent_cards) == 2

    # 7. Session still active
    resp = flask_client.get("/api/session")
    assert resp.get_json()["active"] is True


def test_session_lifecycle(flask_client):
    flask_client.post("/api/session/start")
    resp = flask_client.get("/api/session")
    assert resp.get_json()["active"] is True

    flask_client.post("/api/session/stop")
    resp = flask_client.get("/api/session")
    assert resp.get_json()["active"] is False
