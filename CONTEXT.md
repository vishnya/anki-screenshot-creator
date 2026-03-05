# anki-fox — Project Context

This file is read by the Claude `/anki` skill at the start of every session and updated
at the end. It is the living source of truth for architecture, status, and recent changes.

## What It Does
Press `⌥⇧A` → crosshair screenshot selector → model generates cards → cards added to Anki automatically.

## Key Files
| File | Purpose |
|------|---------|
| `flask_server.py` | Flask app (port 5789): serves web UI, API endpoints, watchdog thread |
| `config.py` | Read/write `~/.anki-fox/config.json` |
| `models.py` | Provider abstraction: generate_cards(image_path, config) |
| `hammerspoon/init.lua` | Hotkey: GET /api/session → screenshot or open browser |
| `anki.zsh` | `anki()` shell function: ensure server running + open browser |
| `web/templates/index.html` | Single-page config + session UI |
| `web/static/style.css` | Dark theme |
| `web/static/app.js` | Deck fetch, save, session control, SSE live updates |
| `launchd/com.anki-fox.plist` | Template; install.sh generates the live plist |

After install, `~/.hammerspoon/init.lua` is a symlink into this repo.
Server auto-starts on login via `~/Library/LaunchAgents/com.anki-fox.plist`.

## Architecture
```
⌥⇧A keypress (Hammerspoon)
  → GET http://localhost:5789/api/session
  → {active: true}  → screencapture -i → PNG to ~/AnkiFox/incoming/
  → {active: false} → hs.urlevent.openURL("http://localhost:5789")

flask_server.py (launchd, always running)
  → serves web UI at /
  → watchdog thread watches ~/AnkiFox/incoming/
  → on new PNG: reads config, calls models.generate_cards(), adds to AnkiConnect
  → SSE stream at /api/events sends progress + done events to browser

Web UI (localhost:5789)
  → user sets deck, provider, model name, API key, custom prompt
  → POST /api/config saves to ~/.anki-fox/config.json (chmod 600)
  → POST /api/session/start sets session_active: true
  → Recent Cards section updates live via SSE
```

## Hotkey Flow
- **⌥⇧A, session inactive** → browser opens to `localhost:5789`
- **⌥⇧A, session active** → screenshot taken immediately (no browser)
- **⌥⇧⌘A** → stops session, reopens browser to reconfigure

## Config Schema (`~/.anki-fox/config.json`)
```json
{
  "session_active": false,
  "deck": "Anatomy",
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-6",
    "base_url": null
  },
  "api_keys": {
    "anthropic": "sk-ant-...",
    "openai": "sk-...",
    "groq": "gsk_...",
    "gemini": "AIza..."
  },
  "custom_prompt": "",
  "deck_prompts": { "Anatomy": "Focus on definitions." }
}
```
File is `chmod 600`. On first creation, `$ANTHROPIC_API_KEY` env var pre-fills the anthropic key.

## Provider Support
| Provider | api_keys key | Base URL | Notes |
|----------|-------------|----------|-------|
| `anthropic` | anthropic | — | anthropic SDK |
| `openai` | openai | — | openai SDK |
| `groq` | groq | `https://api.groq.com/openai/v1` | openai SDK |
| `gemini` | gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | openai SDK, key from aistudio.google.com |
| `custom` | — | user-supplied | openai SDK, no key required |

Model name is a free-text field in the UI; defaults per provider: `claude-sonnet-4-6`, `gpt-4o`, `llama-3.3-70b-versatile`, `gemini-2.0-flash`, `minicpm-v`.

Custom and OpenAI providers pass `response_format: {"type": "json_object"}` to force valid JSON output. `_parse_cards` also has a JSON extraction fallback: if `json.loads` fails, it tries to find and parse the outermost `{...}` from the response before raising an error.

## Web UI Behaviour
- All fields autosave on blur/change to config.json — no explicit save needed
- Last-used deck pre-selected on page load
- "New deck" toggle in the deck field: `+ New` button → text input → Enter to confirm; deck created in Anki when first card is added
- Activity log: persistent scrollable list between status banner and Recent Cards; shows timestamped progress, done (green), and error (red) entries; max 20, clears on Start Session
- Recent Cards: max 10, shows deck badge + first line of back; cards > 1 hr old dimmed to 45% opacity

## Flask API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves index.html |
| GET | `/api/decks` | AnkiConnect deckNames proxy |
| GET | `/api/config` | Returns config.json |
| POST | `/api/config` | Saves config.json (accepted keys: `deck`, `model`, `api_keys`, `custom_prompt`, `deck_prompts`) |
| GET | `/api/session` | Returns `{active, deck}` |
| POST | `/api/session/start` | Sets session_active: true |
| POST | `/api/session/stop` | Sets session_active: false |
| GET | `/api/events` | SSE: `progress`, `done`, `error`, `ping`, `recent` (sent once on connect with in-memory card history) |

## AnkiConnect
- URL: `http://localhost:8765`
- Version: 6
- Test: `curl -s -X POST http://localhost:8765 -d '{"action":"version","version":6}'`

## Known Gotchas
- Anki process name is `python3.x` — detect with `lsof -i :8765`, not `pgrep -x Anki`
- Flask runs with `threaded=True, use_reloader=False` — safe for watchdog thread
- SSE uses per-connection queues broadcast from watchdog thread
- `anki_watcher.py` is now a deprecated stub — don't run it
- Server logs: `tail -f /tmp/anki-fox.log`
- Check server: `launchctl list | grep anki`
- Restart server: `launchctl kickstart -k gui/$UID/com.anki-fox`

## Recent Changes
- 2026-03-01: Fixed freeze on deck select — switched from `hs.execute` to `hs.task.new`
- 2026-03-02: Moved into monorepo at `~/code/anki_fox/`
- 2026-03-02: **Web UI redesign** — replaced hs.chooser with Flask web UI; added launchd agent; multi-provider model support; Hammerspoon simplified to ~30 lines
- 2026-03-02: Added Gemini provider (OpenAI-compat endpoint, no extra SDK)
- 2026-03-02: Renamed `openai_compatible` provider to `custom`
- 2026-03-02: Autosave on blur/change for all config fields; last deck remembered across sessions
- 2026-03-02: "New deck" creation in web UI (no longer needs Hammerspoon chooser)
- 2026-03-02: Recent Cards shows deck badge + back preview; max 10; cards > 1 hr dimmed
- 2026-03-02: Per-deck saved prompts (`deck_prompts` in config); prompt loads/saves on deck switch
- 2026-03-03: install.sh: clone before deps, .venv via uv (not pip/venv), launchd plist uses venv python
- 2026-03-04: install.sh: Hammerspoon section explains purpose + step-by-step Accessibility/Screen Recording permissions
- 2026-03-04: Web UI: Retry button + auto-retry every 5s when Anki not reachable
- 2026-03-04: uninstall.sh: now offers to uninstall Hammerspoon; tests verify full install/uninstall coverage (44 tests)
- 2026-03-04: Activity log: persistent scrollable event log in web UI (progress, done, errors with timestamps)
- 2026-03-04: Screenshot validation: images < 50x50 px rejected as cancelled selections
- 2026-03-04: Duplicate cards reported in done message ("2 card(s) added, 1 duplicate(s) skipped")
- 2026-03-04: `_parse_cards` shows first 200 chars of response on JSON errors; fallback extracts JSON from free text
- 2026-03-04: `response_format: json_object` for custom/OpenAI providers (fixes Ollama garbled output)
- 2026-03-04: Default custom model changed to `minicpm-v`; placeholder shows recommended models (50 tests)
