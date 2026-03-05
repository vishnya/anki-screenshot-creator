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


# ── UI action tests ──────────────────────────────────────────────────────────


class TestSessionLifecycle:
    """Full session start/stop cycle with config changes."""

    def test_start_session_saves_config_and_activates(self, flask_client):
        flask_client.post("/api/config", json={
            "deck": "Biology",
            "model": {"provider": "anthropic", "model_name": "claude-sonnet-4-6", "base_url": None},
            "api_keys": {"anthropic": "sk-test"},
        })
        resp = flask_client.post("/api/session/start")
        assert resp.get_json()["ok"] is True
        session = flask_client.get("/api/session").get_json()
        assert session["active"] is True
        assert session["deck"] == "Biology"

    def test_stop_session_deactivates(self, flask_client):
        flask_client.post("/api/session/start")
        flask_client.post("/api/session/stop")
        assert flask_client.get("/api/session").get_json()["active"] is False

    def test_start_stop_start_works(self, flask_client):
        flask_client.post("/api/config", json={"deck": "D1"})
        flask_client.post("/api/session/start")
        flask_client.post("/api/session/stop")
        flask_client.post("/api/config", json={"deck": "D2"})
        flask_client.post("/api/session/start")
        session = flask_client.get("/api/session").get_json()
        assert session["active"] is True
        assert session["deck"] == "D2"


class TestConfigPersistence:
    """Config changes persist across reads."""

    def test_switch_provider_and_model(self, flask_client):
        flask_client.post("/api/config", json={
            "model": {"provider": "openai", "model_name": "gpt-4o", "base_url": None},
            "api_keys": {"openai": "sk-openai-test"},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["model"]["provider"] == "openai"
        assert conf["model"]["model_name"] == "gpt-4o"
        assert conf["api_keys"]["openai"] == "sk-openai-test"

    def test_switch_to_custom_provider(self, flask_client):
        flask_client.post("/api/config", json={
            "model": {"provider": "custom", "model_name": "minicpm-v", "base_url": "http://localhost:11434/v1"},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["model"]["provider"] == "custom"
        assert conf["model"]["base_url"] == "http://localhost:11434/v1"

    def test_api_key_per_provider_independent(self, flask_client):
        flask_client.post("/api/config", json={
            "api_keys": {"anthropic": "key-a", "openai": "key-o"},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["api_keys"]["anthropic"] == "key-a"
        assert conf["api_keys"]["openai"] == "key-o"

    def test_deck_prompt_saved_per_deck(self, flask_client):
        flask_client.post("/api/config", json={
            "deck": "Bio",
            "custom_prompt": "Focus on cells",
            "deck_prompts": {"Bio": "Focus on cells"},
        })
        flask_client.post("/api/config", json={
            "deck": "Chem",
            "custom_prompt": "Focus on reactions",
            "deck_prompts": {"Bio": "Focus on cells", "Chem": "Focus on reactions"},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["deck_prompts"]["Bio"] == "Focus on cells"
        assert conf["deck_prompts"]["Chem"] == "Focus on reactions"

    def test_clear_deck_prompt(self, flask_client):
        flask_client.post("/api/config", json={
            "deck_prompts": {"Bio": "Focus on cells"},
        })
        flask_client.post("/api/config", json={
            "deck_prompts": {},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["deck_prompts"] == {}


class TestIndexHTML:
    """Verify the HTML page contains expected UI elements."""

    def test_contains_model_details(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert "model-details" in html
        assert "model-summary" in html

    def test_contains_provider_options(self, flask_client):
        html = flask_client.get("/").data.decode()
        for provider in ["anthropic", "openai", "groq", "gemini", "custom"]:
            assert f'value="{provider}"' in html

    def test_contains_session_buttons(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert "btn-start" in html
        assert "btn-stop" in html

    def test_contains_deck_selector(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert 'id="deck"' in html
        assert "btn-new-deck" in html

    def test_contains_fox_logo(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert "fox-logo" in html

    def test_contains_topic_focus(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert "custom-prompt" in html
