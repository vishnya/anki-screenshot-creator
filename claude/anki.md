If the argument is "run tests" or the user asks to run the test suite:
  Run: cd ~/code/anki_fox && /opt/anaconda3/bin/python -m pytest tests/ -v --tb=short
  Report results clearly (pass/fail counts, any failures). Done — no architecture summary needed.

Otherwise (normal session start):
  Read `~/.anki-fox/CONTEXT.md` for project context, then read
  `~/code/anki_fox/flask_server.py` to see the current state of the code.
  Summarize architecture and current status in 5 bullet points, then ask what we're working on today.

  When the session is done, update `~/.anki-fox/CONTEXT.md` — specifically the
  "Recent Changes" section — to reflect what changed, so the next session starts with accurate context.
