"""Playwright UI tests for the Anki Fox web interface.

Starts a real Flask test server on a random port with mocked AnkiConnect,
then drives a headless Chromium browser against it.
"""

import threading

import pytest
from unittest.mock import patch
from werkzeug.serving import make_server

import flask_server
import config as cfg_module


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def live_server(tmp_path, monkeypatch):
    """Start Flask on a random port with mocked AnkiConnect; yield base URL."""
    # Isolate config
    config_dir = tmp_path / ".anki-fox"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(cfg_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_file)

    # Mock AnkiConnect so /api/decks works
    def fake_ankiconnect(action, **params):
        if action == "deckNames":
            return ["TestDeck1", "TestDeck2", "Biology"]
        if action == "findNotes":
            return []
        if action == "notesInfo":
            return []
        return None

    # threaded=True is required because the SSE endpoint (/api/events) holds
    # a persistent connection; without threading, all other requests block.
    server = make_server("127.0.0.1", 0, flask_server.app, threaded=True)
    port = server.socket.getsockname()[1]

    with patch("flask_server._ankiconnect", side_effect=fake_ankiconnect):
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


@pytest.fixture()
def page(live_server, browser):
    """Create a Playwright page at 1280x720 pointed at the live server.

    Uses wait_until='load' instead of 'networkidle' because the SSE
    endpoint (/api/events) keeps a persistent connection that prevents
    networkidle from ever firing. We then wait for the deck select to
    populate as a signal that init() has completed.
    """
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    pg = ctx.new_page()
    pg.goto(live_server, wait_until="load")
    # Wait for JS init() to complete — deck select gets populated with real decks
    pg.locator("#deck option[value='TestDeck1']").wait_for(state="attached", timeout=5000)
    yield pg
    pg.close()
    ctx.close()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_page_loads(page):
    """Title, fox logo, and h1 are visible."""
    assert page.title() == "anki-fox"
    assert page.locator(".fox-logo").is_visible()
    assert page.locator("h1").is_visible()
    assert page.locator("h1").text_content() == "anki-fox"


def test_form_elements_present(page):
    """Deck select, prompt textarea, start button exist; provider is in DOM."""
    assert page.locator("#deck").is_visible()
    assert page.locator("#custom-prompt").is_visible()
    assert page.locator("#btn-start").is_visible()
    # Provider is inside a collapsed <details>, so it's in DOM but not visible
    assert page.locator("#provider").count() == 1


def test_provider_switch_updates_model(page):
    """Changing the provider dropdown updates the model combobox options."""
    # Open model details by clicking the summary
    page.locator("#model-summary").click()
    page.locator("#provider").wait_for(state="visible", timeout=3000)

    # Default is anthropic — check model input has a claude model
    model_val = page.locator("#model-name").input_value()
    assert "claude" in model_val.lower()

    # Switch to openai via JS dispatch (Playwright select_option doesn't
    # reliably fire the change listener in this app's setup)
    page.evaluate("""() => {
        const sel = document.querySelector('#provider');
        sel.value = 'openai';
        sel.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    # Wait for the model summary to reflect the new provider
    page.wait_for_function(
        "() => document.getElementById('model-summary-text').textContent.includes('GPT')",
        timeout=5000,
    )

    model_val = page.locator("#model-name").input_value()
    assert "gpt" in model_val.lower() or "o3" in model_val.lower() or "o1" in model_val.lower(), \
        f"Expected GPT/o3/o1 model but got: {model_val}"

    # Switch to gemini
    page.evaluate("""() => {
        const sel = document.querySelector('#provider');
        sel.value = 'gemini';
        sel.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_function(
        "() => document.getElementById('model-summary-text').textContent.includes('Gemini')",
        timeout=5000,
    )
    model_val = page.locator("#model-name").input_value()
    assert "gemini" in model_val.lower(), f"Expected gemini model but got: {model_val}"


def test_start_stop_buttons_toggle(page):
    """Start button is visible initially; stop button is hidden."""
    assert page.locator("#btn-start").is_visible()
    assert not page.locator("#btn-stop").is_visible()


def test_model_details_collapsible(page):
    """The model details section opens and closes on click."""
    details = page.locator("#model-details")

    # Initially closed — provider select should not be visible
    assert not details.get_attribute("open")
    assert not page.locator("#provider").is_visible()

    # Open it
    page.locator("#model-summary").click()
    page.wait_for_timeout(300)
    assert details.get_attribute("open") is not None
    assert page.locator("#provider").is_visible()

    # Close it
    page.locator("#model-summary").click()
    page.wait_for_timeout(300)
    # After closing, open attribute is removed
    assert not details.get_attribute("open")


def test_empty_states(page):
    """Activity log shows 'No activity yet', cards show 'No cards yet'."""
    activity = page.locator("#activity-log")
    assert "No activity yet" in activity.text_content()

    cards = page.locator("#cards-list")
    assert "No cards yet" in cards.text_content()


def test_new_deck_button_shows_input(page):
    """Clicking 'New' shows the new-deck input row."""
    new_row = page.locator("#deck-new-row")
    assert not new_row.is_visible()

    page.locator("#btn-new-deck").click()
    page.wait_for_timeout(200)

    assert new_row.is_visible()
    assert page.locator("#deck-new-input").is_visible()
    # Deck row should be hidden while new-deck input is shown
    assert not page.locator("#deck-row").is_visible()


def test_deck_loading_state(tmp_path, monkeypatch, browser):
    """When Anki is unreachable the deck select shows a fallback message.

    Uses a failing AnkiConnect mock so /api/decks returns 503, which makes
    the JS show either 'Loading decks...' (initial HTML) or
    'Anki not reachable' (after JS error handling).
    """
    config_dir = tmp_path / ".anki-fox"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(cfg_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_file)

    def failing_ankiconnect(action, **params):
        raise ConnectionError("Anki not running")

    server = make_server("127.0.0.1", 0, flask_server.app, threaded=True)
    port = server.socket.getsockname()[1]

    with patch("flask_server._ankiconnect", side_effect=failing_ankiconnect):
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 720})
            pg = ctx.new_page()
            pg.goto(f"http://127.0.0.1:{port}", wait_until="load")
            # Wait for JS to process the /api/decks failure
            pg.wait_for_timeout(1000)
            deck = pg.locator("#deck")
            text = deck.text_content()
            assert "Loading decks" in text or "Anki not reachable" in text
            pg.close()
            ctx.close()
        finally:
            server.shutdown()


def test_offline_banner_hidden(page):
    """Offline banner should not be visible on initial load."""
    assert not page.locator("#offline-banner").is_visible()


def test_video_config_hidden(page):
    """Video config panel should be hidden by default."""
    assert not page.locator("#source-video-config").is_visible()


# ── UX checks (shared library) ───────────────────────────────────────────────

import sys, os
sys.path.insert(0, os.path.expanduser("~/code"))
from ux_checks import (
    check_no_horizontal_scroll,
    check_font_readability,
    check_button_uniformity,
    check_clickable_not_obscured,
    check_no_text_overflow,
    check_elements_in_viewport,
    check_uniform_sibling_sizing,
    check_consistent_spacing,
)


def test_no_horizontal_scroll(page):
    """Page should not scroll horizontally at 1280x720."""
    issues = check_no_horizontal_scroll(page)
    assert not issues, f"Horizontal scroll detected: {issues}"


def test_font_readability(page):
    """No visible text should be below 11px."""
    issues = check_font_readability(page, min_size_px=11)
    assert not issues, f"Text too small: {issues}"


def test_button_uniformity(page):
    """Sibling buttons should have consistent height."""
    issues = check_button_uniformity(page)
    assert not issues, f"Button height inconsistency: {issues}"


def test_form_field_uniform_width(page):
    """Form inputs and selects should have consistent full width.

    All .field containers' inputs/selects/textareas should fill their parent
    uniformly — no one field randomly narrower than the others.
    """
    issues = page.evaluate("""() => {
        const issues = [];
        const fields = document.querySelectorAll('.field');
        const widths = [];
        for (const field of fields) {
            const style = getComputedStyle(field);
            if (style.display === 'none' || field.offsetParent === null) continue;
            const input = field.querySelector('input, select, textarea');
            if (!input) continue;
            const inputStyle = getComputedStyle(input);
            if (inputStyle.display === 'none' || input.offsetParent === null) continue;
            const rect = input.getBoundingClientRect();
            if (rect.width === 0) continue;
            const parentRect = field.getBoundingClientRect();
            if (parentRect.width === 0) continue;
            widths.push({
                id: input.id || input.tagName,
                ratio: rect.width / parentRect.width,
                width: rect.width,
            });
        }
        // All visible top-level form fields should have similar width ratios
        if (widths.length >= 2) {
            const ratios = widths.map(w => w.ratio);
            const maxR = Math.max(...ratios);
            const minR = Math.min(...ratios);
            if (maxR - minR > 0.15) {
                const narrow = widths.filter(w => w.ratio < maxR - 0.15);
                for (const n of narrow) {
                    issues.push(`#${n.id}: width ratio ${(n.ratio * 100).toFixed(0)}% vs max ${(maxR * 100).toFixed(0)}%`);
                }
            }
        }
        return issues;
    }""")
    assert not issues, f"Form field width inconsistency: {issues}"


def test_clickable_not_obscured(page):
    """No visible buttons or links should be hidden behind other elements."""
    issues = check_clickable_not_obscured(page)
    assert not issues, f"Clickable elements obscured: {issues}"


def test_key_elements_in_viewport(page):
    """Main form, activity log, and cards list should be within viewport bounds."""
    issues = check_elements_in_viewport(page, [
        "#deck",
        "#custom-prompt",
        "#btn-start",
        "#activity-log",
        "#cards-list",
    ])
    assert not issues, f"Key elements outside viewport: {issues}"


def test_no_text_overflow(page):
    """No text should be truncated without ellipsis."""
    issues = check_no_text_overflow(page)
    assert not issues, f"Text overflow without ellipsis: {issues}"


def test_section_spacing_consistent(page):
    """Spacing between form fields should be consistent.

    The .container has multiple .field children; gaps between them should
    not vary by more than 4px.
    """
    issues = check_consistent_spacing(page, ".container", ".field", tolerance_px=4)
    assert not issues, f"Inconsistent field spacing: {issues}"
