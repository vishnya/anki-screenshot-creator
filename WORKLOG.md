# Worklog

Recent session handoff notes. Read on session start, append before committing.
Keep only the last 10 entries. Each entry: date, device, what was done.

---

### 2026-03-20 | Mac
- Fixed multi-screenshot mode: removed 0.3s race condition in Hammerspoon callback, disable Enter/Escape hotkeys during screencapture so keys reach screencapture normally, track pending task for clean cancel/finish
- Added 16 new tests in test_multi_screenshot.py (stitching, watchdog integration, source cycling)
- Updated /anki slash command to point to current project files (was referencing deleted ~/.anki-screenshot-creator/)
- Updated anki_watcher.md memory with recent changes
- 280 tests passing, pushed to GitHub

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
