"""Tests for code formatting rules in the card generation prompt.

Background: Anki renders HTML, not markdown. If the model emits markdown
backticks like `.shape`, they show up as literal characters on the card.
The prompt must instruct the model to use <code>...</code> tags instead.
"""
import models


class TestPromptCodeRules:
    """Verify the prompt instructs the LLM to use HTML <code> tags, not backticks."""

    def test_code_formatting_section_in_prompt(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        assert "CODE FORMATTING:" in prompt

    def test_code_tag_mentioned(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        assert "<code>" in prompt and "</code>" in prompt

    def test_warns_against_markdown_backticks(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        # Must explicitly tell the model not to use markdown backticks.
        assert "markdown" in prompt.lower()
        assert "backtick" in prompt.lower()

    def test_selfcheck_includes_code(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        selfcheck_pos = prompt.index("SELF-CHECK:")
        selfcheck_text = prompt[selfcheck_pos:]
        assert "<code>" in selfcheck_text
