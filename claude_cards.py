#!/usr/bin/env python3
"""
Create Anki cards from Claude Code sessions.
Generates bidirectional cards for system design and AI concepts.

Usage:
    python claude_cards.py "concept" "definition" "scenario" "example" [--type sysdesign|ai]

Args:
    concept:    The term (e.g., "sticky bit")
    definition: Plain-language explanation of the concept
    scenario:   A description of the problem/symptoms that this concept explains.
                Must NOT name the concept — this is the front of the recall card.
                Must contain enough context for the reader to figure out the answer.
    example:    How the concept applied in our real work. Can name the concept.

Cards created (bidirectional):
  1. Recall: scenario (front) → concept + definition + example (back)
     Tests: "I see this situation, what's the concept?"
  2. Define: concept name (front) → definition + example (back)
     Tests: "I know this term, what does it mean and when did we use it?"

Examples:
    python claude_cards.py \
        "sticky bit" \
        "A Linux permission rule on directories (like /tmp) that prevents users from deleting files they don't own, even if the directory is world-writable" \
        "A server process running as root created temp files in /tmp. A different user tried to delete them and got 'Operation not permitted', even though /tmp has write permissions for all users. What filesystem rule caused this?" \
        "In Walkie, the Node server ran as root and the claude user couldn't clean up root-owned temp files in /tmp. Fixed by eliminating temp files entirely."
"""

import json
import sys
import argparse
import requests

ANKICONNECT_URL = "http://localhost:8765"
SYSDESIGN_DECK = "Claude System Design Learnings"
AI_DECK = "Claude AI Learnings"


def ankiconnect(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    resp = requests.post(ANKICONNECT_URL, json=payload, timeout=10)
    result = resp.json()
    if result.get("error"):
        raise Exception(f"AnkiConnect error: {result['error']}")
    return result["result"]


def ensure_deck(deck_name):
    """Create deck if it doesn't exist."""
    decks = ankiconnect("deckNames")
    if deck_name not in decks:
        ankiconnect("createDeck", deck=deck_name)
        print(f"Created deck: {deck_name}")


def create_cards(concept, definition, scenario, example, deck, tags=None):
    """Create bidirectional Anki cards for a concept.

    Card 1 (recall): scenario on front → concept + definition + example on back
    Card 2 (define): concept name on front → definition + example on back
    """
    if tags is None:
        tags = []
    tags.append("claude-session")

    ensure_deck(deck)
    created = 0

    # Card 1 — Recall: scenario → concept
    # Front has enough info to figure out the answer. Does NOT name the concept.
    front1 = f"{scenario}"
    back1 = (
        f"<b>{concept}</b>"
        f"<br><br>"
        f"{definition}"
        f"<br><br>"
        f"<i>Real example:</i> {example}"
    )

    try:
        ankiconnect("addNote", note={
            "deckName": deck,
            "modelName": "Basic",
            "fields": {"Front": front1, "Back": back1},
            "tags": tags,
            "options": {"allowDuplicate": False},
        })
        created += 1
        print(f"  Recall card: scenario → {concept}")
    except Exception as e:
        if "duplicate" in str(e).lower():
            print(f"  Recall card: skipped (duplicate)")
        else:
            raise

    # Card 2 — Define: concept → definition + example
    # Front names the concept as a natural question. Back explains plainly.
    front2 = f"What is a <b>{concept}</b>?"
    back2 = (
        f"{definition}"
        f"<br><br>"
        f"<i>Real example:</i> {example}"
    )

    try:
        ankiconnect("addNote", note={
            "deckName": deck,
            "modelName": "Basic",
            "fields": {"Front": front2, "Back": back2},
            "tags": tags,
            "options": {"allowDuplicate": False},
        })
        created += 1
        print(f"  Define card: {concept} → definition")
    except Exception as e:
        if "duplicate" in str(e).lower():
            print(f"  Define card: skipped (duplicate)")
        else:
            raise

    return created


def main():
    parser = argparse.ArgumentParser(description="Create Anki cards from Claude sessions")
    parser.add_argument("concept", help="The term or concept name")
    parser.add_argument("definition", help="Plain-language definition")
    parser.add_argument("scenario", help="Problem description WITHOUT naming the concept (front of recall card)")
    parser.add_argument("example", help="How it applied in our real work (can name the concept)")
    parser.add_argument("--deck", default=None, help=f"Deck name (default: {SYSDESIGN_DECK})")
    parser.add_argument("--type", choices=["sysdesign", "ai"], default="sysdesign",
                        help="Type of concept (determines default deck)")
    parser.add_argument("--tags", nargs="*", default=[], help="Additional tags")

    args = parser.parse_args()

    deck = args.deck or (AI_DECK if args.type == "ai" else SYSDESIGN_DECK)
    tags = args.tags + [f"type:{args.type}"]

    print(f"Creating cards in '{deck}':")
    created = create_cards(args.concept, args.definition, args.scenario, args.example, deck, tags)
    print(f"Done: {created} cards created")


if __name__ == "__main__":
    main()
