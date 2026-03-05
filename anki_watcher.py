"""
anki_watcher.py — DEPRECATED

The watchdog logic has moved into flask_server.py which runs as a background
launchd agent.  The card-generation logic lives in models.py.

To start the server manually:
    python flask_server.py

It listens on http://localhost:5789 and watches ~/AnkiFox/incoming/
for new screenshots automatically.
"""

if __name__ == "__main__":
    print("anki_watcher.py is no longer used.")
    print("The server runs automatically via launchd.")
    print("Open http://localhost:5789 to configure, or press ⌥⇧A.")
