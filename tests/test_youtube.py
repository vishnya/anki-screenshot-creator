"""Tests for YouTube transcript module and YouTube-related API endpoints."""

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

import youtube
import flask_server
import models


# ── youtube.py unit tests ──────────────────────────────────────────────────────


class TestExtractVideoId:
    """Test video ID extraction from various URL formats."""

    def test_standard_watch_url(self):
        assert youtube.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert youtube.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert youtube.extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        assert youtube.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ&t=120") == "dQw4w9WgXcQ"

    def test_bare_video_id(self):
        assert youtube.extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url_returns_none(self):
        assert youtube.extract_video_id("not-a-url") is None

    def test_empty_string_returns_none(self):
        assert youtube.extract_video_id("") is None

    def test_whitespace_stripped(self):
        assert youtube.extract_video_id("  dQw4w9WgXcQ  ") == "dQw4w9WgXcQ"

    def test_v_url_format(self):
        assert youtube.extract_video_id("https://youtube.com/v/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


class TestGetTranscriptChunk:
    """Test transcript chunking around timestamps."""

    @pytest.fixture
    def sample_transcript(self):
        return [
            {"text": "Hello everyone", "start": 0.0, "duration": 3.0},
            {"text": "today we talk about math", "start": 3.0, "duration": 4.0},
            {"text": "first topic is algebra", "start": 10.0, "duration": 5.0},
            {"text": "equations are fun", "start": 15.0, "duration": 3.0},
            {"text": "now let us discuss calculus", "start": 30.0, "duration": 5.0},
            {"text": "derivatives measure change", "start": 60.0, "duration": 4.0},
            {"text": "integrals are the reverse", "start": 64.0, "duration": 4.0},
            {"text": "thanks for watching", "start": 120.0, "duration": 3.0},
        ]

    def test_chunk_at_beginning(self, sample_transcript):
        chunk = youtube.get_transcript_chunk(sample_transcript, 0.0, window=10.0)
        assert "Hello everyone" in chunk
        assert "today we talk about math" in chunk
        assert "first topic is algebra" in chunk

    def test_chunk_at_middle(self, sample_transcript):
        chunk = youtube.get_transcript_chunk(sample_transcript, 62.0, window=10.0)
        assert "derivatives measure change" in chunk
        assert "integrals are the reverse" in chunk
        assert "Hello everyone" not in chunk

    def test_chunk_at_end(self, sample_transcript):
        chunk = youtube.get_transcript_chunk(sample_transcript, 120.0, window=10.0)
        assert "thanks for watching" in chunk
        assert "Hello everyone" not in chunk

    def test_empty_transcript(self):
        chunk = youtube.get_transcript_chunk([], 10.0)
        assert chunk == ""

    def test_default_window_30s(self, sample_transcript):
        chunk = youtube.get_transcript_chunk(sample_transcript, 15.0)
        # Default 30s window: 0 to 45s
        assert "Hello everyone" in chunk
        assert "equations are fun" in chunk
        assert "now let us discuss calculus" in chunk

    def test_no_segments_in_range(self, sample_transcript):
        chunk = youtube.get_transcript_chunk(sample_transcript, 90.0, window=5.0)
        assert chunk == ""


class TestFormatTimestamp:
    """Test timestamp formatting."""

    def test_zero(self):
        assert youtube.format_timestamp(0) == "0:00"

    def test_seconds(self):
        assert youtube.format_timestamp(45) == "0:45"

    def test_minutes(self):
        assert youtube.format_timestamp(125) == "2:05"

    def test_hours(self):
        assert youtube.format_timestamp(3661) == "1:01:01"

    def test_float_truncated(self):
        assert youtube.format_timestamp(90.7) == "1:30"


class TestVideoMeta:
    """Test VideoMeta dataclass."""

    def test_to_dict(self):
        meta = youtube.VideoMeta(
            video_id="abc123",
            title="Test Video",
            duration=120.0,
            transcript=[{"text": "hello", "start": 0, "duration": 3}],
        )
        d = meta.to_dict()
        assert d["video_id"] == "abc123"
        assert d["title"] == "Test Video"
        assert d["duration"] == 120.0
        assert d["transcript_loaded"] is True
        assert d["segment_count"] == 1

    def test_to_dict_no_transcript(self):
        meta = youtube.VideoMeta(video_id="abc123", title="Test")
        d = meta.to_dict()
        assert d["transcript_loaded"] is False
        assert d["segment_count"] == 0


class TestFetchTranscript:
    """Test transcript fetching (mocked)."""

    def test_fetch_transcript_success(self):
        @dataclass
        class MockSegment:
            text: str
            start: float
            duration: float

        mock_api = MagicMock()
        mock_api.fetch.return_value = [
            MockSegment(text="Hello", start=0.0, duration=3.0),
            MockSegment(text="World", start=3.0, duration=2.0),
        ]
        with patch("youtube.YouTubeTranscriptApi", return_value=mock_api):
            result = youtube.fetch_transcript("abc123")
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[1]["start"] == 3.0

    def test_fetch_transcript_not_installed(self):
        with patch.object(youtube, "HAS_TRANSCRIPT_API", False):
            with pytest.raises(ImportError, match="youtube-transcript-api"):
                youtube.fetch_transcript("abc123")


class TestFetchVideoTitle:
    """Test title fetching (mocked)."""

    def test_title_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"title": "My Great Video"}
        mock_resp.raise_for_status = MagicMock()
        import requests as req_mod
        with patch.object(req_mod, "get", return_value=mock_resp):
            title = youtube.fetch_video_title("abc123")
        assert title == "My Great Video"

    def test_title_failure_returns_video_id(self):
        import requests as req_mod
        with patch.object(req_mod, "get", side_effect=Exception("network")):
            title = youtube.fetch_video_title("abc123")
        assert title == "abc123"


class TestLoadVideo:
    """Test the full load_video flow."""

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not extract video ID"):
            youtube.load_video("not-a-url")

    def test_load_video_success(self):
        @dataclass
        class MockSegment:
            text: str
            start: float
            duration: float

        mock_api = MagicMock()
        mock_api.fetch.return_value = [
            MockSegment(text="Hello", start=0.0, duration=3.0),
            MockSegment(text="World", start=3.0, duration=2.0),
        ]
        with patch("youtube.YouTubeTranscriptApi", return_value=mock_api), \
             patch("youtube.fetch_video_title", return_value="Test Title"):
            video = youtube.load_video("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert video.video_id == "dQw4w9WgXcQ"
        assert video.title == "Test Title"
        assert video.duration == 5.0
        assert len(video.transcript) == 2


# ── Flask API endpoint tests ──────────────────────────────────────────────────


class TestYouTubeLoadEndpoint:
    """Test POST /api/youtube/load."""

    def test_load_success(self, flask_client):
        @dataclass
        class MockSegment:
            text: str
            start: float
            duration: float

        mock_api = MagicMock()
        mock_api.fetch.return_value = [
            MockSegment(text="Hello", start=0.0, duration=3.0),
        ]
        with patch("youtube.YouTubeTranscriptApi", return_value=mock_api), \
             patch("youtube.fetch_video_title", return_value="My Video"):
            resp = flask_client.post("/api/youtube/load", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert data["title"] == "My Video"
        assert data["transcript_loaded"] is True

    def test_load_no_url(self, flask_client):
        resp = flask_client.post("/api/youtube/load", json={"url": ""})
        assert resp.status_code == 400

    def test_load_invalid_url(self, flask_client):
        resp = flask_client.post("/api/youtube/load", json={"url": "not-a-url"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_load_transcript_failure(self, flask_client):
        with patch("youtube.load_video", side_effect=Exception("No transcript")):
            resp = flask_client.post("/api/youtube/load", json={"url": "https://youtube.com/watch?v=abc12345678"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestYouTubeStatusEndpoint:
    """Test GET /api/youtube/status."""

    def test_status_no_video(self, flask_client):
        flask_server._loaded_video = None
        resp = flask_client.get("/api/youtube/status")
        assert resp.status_code == 200
        assert resp.get_json() is None

    def test_status_with_video(self, flask_client):
        flask_server._loaded_video = youtube.VideoMeta(
            video_id="abc123", title="Test", duration=60.0,
            transcript=[{"text": "hi", "start": 0, "duration": 2}],
        )
        resp = flask_client.get("/api/youtube/status")
        data = resp.get_json()
        assert data["video_id"] == "abc123"
        assert data["transcript_loaded"] is True


class TestYouTubeClearEndpoint:
    """Test POST /api/youtube/clear."""

    def test_clear(self, flask_client):
        flask_server._loaded_video = youtube.VideoMeta(video_id="abc", title="T")
        resp = flask_client.post("/api/youtube/clear")
        assert resp.status_code == 200
        assert flask_server._loaded_video is None


# ── Config deck_sources tests ─────────────────────────────────────────────────


class TestDeckSources:
    """Test deck_sources config persistence."""

    def test_save_deck_sources(self, flask_client):
        flask_client.post("/api/config", json={
            "deck_sources": {"Bio": {"source": "video", "youtube_url": "https://youtube.com/watch?v=abc123"}},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["deck_sources"]["Bio"]["source"] == "video"
        assert conf["deck_sources"]["Bio"]["youtube_url"] == "https://youtube.com/watch?v=abc123"

    def test_empty_deck_sources_default(self, flask_client):
        conf = flask_client.get("/api/config").get_json()
        assert conf["deck_sources"] == {}

    def test_switch_source_back_to_screen(self, flask_client):
        flask_client.post("/api/config", json={
            "deck_sources": {"Bio": {"source": "video"}},
        })
        flask_client.post("/api/config", json={
            "deck_sources": {},
        })
        conf = flask_client.get("/api/config").get_json()
        assert conf["deck_sources"] == {}


# ── models.py transcript context tests ────────────────────────────────────────


class TestBuildPromptWithTranscript:
    """Test _build_prompt with transcript context injection."""

    def test_no_transcript_returns_base(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        assert "TRANSCRIPT CONTEXT" not in prompt

    def test_transcript_appears_before_rules(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "mitochondria are the powerhouse of the cell",
            "timestamp": 42.0,
        })
        assert "TRANSCRIPT CONTEXT" in prompt
        rules_pos = prompt.index("RULES:")
        transcript_pos = prompt.index("TRANSCRIPT CONTEXT")
        assert transcript_pos < rules_pos

    def test_transcript_includes_timestamp(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "hello world",
            "timestamp": 125.0,
        })
        assert "2:05" in prompt

    def test_transcript_includes_video_title(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "hello world",
            "video_title": "My Great Lecture",
        })
        assert "My Great Lecture" in prompt

    def test_transcript_with_custom_prompt_both_present(self):
        prompt = models._build_prompt({
            "custom_prompt": "Focus on biology",
            "transcript_context": "cells divide by mitosis",
            "timestamp": 60.0,
        })
        assert "TRANSCRIPT CONTEXT" in prompt
        assert "Focus on biology" in prompt
        assert "cells divide by mitosis" in prompt

    def test_transcript_guidance_text(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "some text",
        })
        assert "Use this transcript alongside the screenshot" in prompt

    def test_empty_transcript_ignored(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "   ",
        })
        assert "TRANSCRIPT CONTEXT" not in prompt

    def test_transcript_with_deck_context(self):
        prompt = models._build_prompt({
            "custom_prompt": "",
            "transcript_context": "neural networks learn via backpropagation",
            "timestamp": 300.0,
            "deck_context": [
                {"front": "What is a neuron?", "back": "A computation unit", "tags": ["ml"]},
            ],
        })
        assert "TRANSCRIPT CONTEXT" in prompt
        assert "EXISTING CARDS" in prompt
        assert "neural networks" in prompt


# ── Screenshot handler with video source tests ────────────────────────────────


class TestScreenshotHandlerVideoSource:
    """Test ScreenshotHandler.on_created with video source mode."""

    def test_video_source_adds_transcript_context(self, flask_client, tiny_png, mock_ankiconnect):
        """When source=video and video loaded, transcript context is passed to generate_cards."""
        import config as cfg

        # Set up config with video source
        conf = cfg.load()
        conf["session_active"] = True
        conf["deck"] = "TestDeck"
        conf["deck_sources"] = {"TestDeck": {"source": "video"}}
        conf["api_keys"] = {"anthropic": "sk-test"}
        cfg.save(conf)

        # Load a video — transcript segments near end so they're in range of duration fallback
        flask_server._loaded_video = youtube.VideoMeta(
            video_id="test123",
            title="Test Lecture",
            duration=120.0,
            transcript=[
                {"text": "this is about biology", "start": 95.0, "duration": 5.0},
                {"text": "cells are the building blocks of life", "start": 100.0, "duration": 5.0},
            ],
        )

        cards = [{"front": "What are cells?", "back": "Building blocks of life", "tags": ["bio"], "is_image_card": False}]

        with patch("models.generate_cards", return_value=cards) as mock_gen, \
             patch("time.sleep"):
            handler = flask_server.ScreenshotHandler()
            event = MagicMock()
            event.is_directory = False
            event.src_path = tiny_png
            handler.on_created(event)

            # Verify generate_cards was called with transcript context
            assert mock_gen.called
            call_conf = mock_gen.call_args[0][1]
            assert "transcript_context" in call_conf
            assert "biology" in call_conf["transcript_context"]
            assert call_conf["video_id"] == "test123"

    def test_screen_source_no_transcript(self, flask_client, tiny_png, mock_ankiconnect):
        """When source=screen, no transcript context is passed."""
        import config as cfg

        conf = cfg.load()
        conf["session_active"] = True
        conf["deck"] = "TestDeck"
        conf["deck_sources"] = {}  # screen is default
        conf["api_keys"] = {"anthropic": "sk-test"}
        cfg.save(conf)

        cards = [{"front": "Q?", "back": "A", "tags": [], "is_image_card": False}]

        with patch("models.generate_cards", return_value=cards) as mock_gen, \
             patch("time.sleep"):
            handler = flask_server.ScreenshotHandler()
            event = MagicMock()
            event.is_directory = False
            event.src_path = tiny_png
            handler.on_created(event)

            assert mock_gen.called
            call_conf = mock_gen.call_args[0][1]
            assert "transcript_context" not in call_conf


# ── HTML UI element tests ─────────────────────────────────────────────────────


class TestSourceSelectorHTML:
    """Verify the HTML page contains source selector elements."""

    def test_contains_source_details(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert "source-details" in html
        assert "source-summary" in html

    def test_contains_source_pills(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert 'data-source="screen"' in html
        assert 'data-source="video"' in html

    def test_contains_youtube_url_input(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert 'id="youtube-url"' in html
        assert 'id="btn-load-video"' in html

    def test_contains_video_info(self, flask_client):
        html = flask_client.get("/").data.decode()
        assert 'id="video-info"' in html
        assert 'id="video-title"' in html

    def test_video_config_hidden_by_default(self, flask_client):
        html = flask_client.get("/").data.decode()
        # The source-video-config div should have the hidden class
        assert 'class="source-video-config hidden"' in html
