# Worklog

Recent session handoff notes. Read on session start, append before committing.
Keep only the last 10 entries. Each entry: date, device, what was done.

---

### 2026-03-20 | Mac
- Fixed multi-screenshot mode: screencapture rejects dot-prefixed filenames, renamed .multi_ to multi_; also fixed race condition and key interference in Hammerspoon
- Added claude-code provider: shells out to `claude` CLI for subscription-based card generation (no API key needed). New dropdown option "Claude (subscription)" at top of provider list
- Added computation card rules to prompt: front must give all inputs, back shows formula + names broader concept
- Updated /anki slash command and anki_watcher.md memory
- 311 tests passing (29 new for claude-code, 16 for multi-screenshot, 2 for prompt), pushed to GitHub

### 2026-03-17 | Mac
- Added 8 UX check tests to test_ui.py using shared ~/code/ux_checks/ library
- Tests: horizontal scroll, font readability, button uniformity, form field width, clickable not obscured, key elements in viewport, text overflow, section spacing
- All 18 UI tests passing

### 2026-03-15 | Mac
- Added YouTube video study mode: load video, fetch transcript, chunk by timestamp
- Three capture modes: screen (default), multi-screenshot stitching, video
- Chrome extension for exact YouTube playback position capture
- Video-sourced cards get yt-HHMMSS timestamp tags and YouTube badges in recent list
- Source mode cycling via hotkey (Opt+Shift+M) and API
- Per-deck source configuration persistence in config
- Comprehensive test suite: 246 tests passing
- Pushed to GitHub via subtree
