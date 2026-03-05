import pytest
from unittest.mock import patch


def test_index_returns_html(flask_client):
    resp = flask_client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower()


def test_get_config(flask_client):
    resp = flask_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "deck" in data
    assert "session_active" in data


def test_post_config_updates_deck(flask_client):
    resp = flask_client.post("/api/config", json={"deck": "MyDeck"})
    assert resp.status_code == 200
    resp2 = flask_client.get("/api/config")
    assert resp2.get_json()["deck"] == "MyDeck"


def test_post_config_ignores_unknown_keys(flask_client):
    resp = flask_client.post("/api/config", json={"unknown_key": "value"})
    assert resp.status_code == 200
    conf = flask_client.get("/api/config").get_json()
    assert "unknown_key" not in conf


def test_get_session_inactive(flask_client):
    resp = flask_client.get("/api/session")
    assert resp.status_code == 200
    assert resp.get_json()["active"] is False


def test_session_start(flask_client):
    resp = flask_client.post("/api/session/start")
    assert resp.status_code == 200
    resp2 = flask_client.get("/api/session")
    assert resp2.get_json()["active"] is True


def test_session_stop(flask_client):
    flask_client.post("/api/session/start")
    flask_client.post("/api/session/stop")
    resp = flask_client.get("/api/session")
    assert resp.get_json()["active"] is False


def test_api_decks_success(flask_client, mock_ankiconnect):
    resp = flask_client.get("/api/decks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == ["Deck1", "Deck2"]


def test_api_decks_error(flask_client):
    with patch("flask_server._ankiconnect", side_effect=Exception("Anki not running")):
        resp = flask_client.get("/api/decks")
    assert resp.status_code == 503
    assert "error" in resp.get_json()
