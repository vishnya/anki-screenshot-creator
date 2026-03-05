import os
import pytest
from PIL import Image, ImageDraw, ImageFont

import models


class TestBuildPrompt:
    """Verify _build_prompt places user instructions prominently."""

    def test_no_custom_prompt_returns_base(self):
        prompt = models._build_prompt({"custom_prompt": ""})
        assert prompt == models.PROMPT_TEMPLATE

    def test_custom_prompt_appears_before_rules(self):
        prompt = models._build_prompt({"custom_prompt": "Rhyme everything"})
        rules_pos = prompt.index("RULES:")
        user_pos = prompt.index("Rhyme everything")
        assert user_pos < rules_pos, "User instruction should appear before RULES"

    def test_custom_prompt_in_header_block(self):
        prompt = models._build_prompt({"custom_prompt": "Focus on cells"})
        assert "IMPORTANT — USER INSTRUCTION (follow this exactly):" in prompt
        assert "Focus on cells" in prompt

    def test_custom_prompt_reinforced_in_selfcheck(self):
        prompt = models._build_prompt({"custom_prompt": "Use rhymes"})
        # Should appear twice: once in header, once in self-check
        assert prompt.count("Use rhymes") == 2
        selfcheck_pos = prompt.index("SELF-CHECK:")
        second_occurrence = prompt.index("Use rhymes", prompt.index("Use rhymes") + 1)
        assert second_occurrence > selfcheck_pos, "Should be reinforced after SELF-CHECK"

    def test_whitespace_only_prompt_returns_base(self):
        prompt = models._build_prompt({"custom_prompt": "   \n  "})
        assert prompt == models.PROMPT_TEMPLATE


class TestRhymeAdherence:
    """Lightweight integration test: verify the model follows a rhyming prompt."""

    @pytest.fixture
    def text_png(self, tmp_path):
        """Create a screenshot with readable text content."""
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "Mitochondria are the powerhouse of the cell.\n"
                            "They produce ATP through oxidative phosphorylation.\n"
                            "The inner membrane has many folds called cristae.",
                  fill=(0, 0, 0))
        path = tmp_path / "textbook_screenshot.png"
        img.save(str(path))
        return str(path)

    @pytest.fixture
    def rhyme_config(self):
        return {
            "model": {"provider": "anthropic", "model_name": "claude-haiku-4-5"},
            "api_keys": {"anthropic": ""},
            "custom_prompt": "Write the back of every card as a rhyming couplet.",
        }

    @pytest.mark.integration
    def test_rhyming_prompt_produces_rhymes(self, text_png, rhyme_config):
        """Call the real API with a rhyming instruction and check output rhymes."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        rhyme_config["api_keys"]["anthropic"] = api_key

        cards = models.generate_cards(text_png, rhyme_config)
        assert len(cards) >= 1, "Should generate at least one card"

        # Heuristic: at least one card's back has two lines whose last words
        # share a similar ending (last 2+ chars match = likely rhyme).
        def last_word(line):
            words = line.strip().rstrip(".,!?;:").split()
            return words[-1].lower() if words else ""

        rhyme_found = False
        for card in cards:
            lines = [l for l in card["back"].split("\n") if l.strip()]
            if len(lines) >= 2:
                w1 = last_word(lines[0])
                w2 = last_word(lines[1])
                if len(w1) >= 2 and len(w2) >= 2 and w1[-2:] == w2[-2:]:
                    rhyme_found = True
                    break

        assert rhyme_found, (
            f"Expected at least one card with rhyming couplet on the back. "
            f"Got backs: {[c['back'] for c in cards]}"
        )
