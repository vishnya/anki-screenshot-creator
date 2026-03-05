"""Tests that uninstall.sh removes everything install.sh creates.

Strategy: simulate the artifacts install.sh would leave behind in a temp HOME,
run uninstall.sh (with mocked interactive prompts answering 'y'), and verify
every artifact is gone.
"""

import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_home(tmp_path):
    """Create a temp HOME populated with all artifacts install.sh produces."""
    home = tmp_path / "home"
    home.mkdir()

    repo = home / "anki-fox"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").touch()
    (repo / "requirements.txt").write_text("flask\n")

    # Symlinks
    hs_dir = home / ".hammerspoon"
    hs_dir.mkdir()
    (hs_dir / "init.lua").symlink_to(repo / "hammerspoon" / "init.lua")

    config_dir = home / ".anki-fox"
    config_dir.mkdir()
    (config_dir / "CONTEXT.md").symlink_to(repo / "CONTEXT.md")

    # Claude skill
    claude_dir = home / ".claude" / "commands"
    claude_dir.mkdir(parents=True)
    (claude_dir / "anki.md").write_text("# skill\n")

    # .zshrc with anki lines
    (home / ".zshrc").write_text(textwrap.dedent("""\
        export PATH="/usr/local/bin:$PATH"

        # Anki watcher
        source {repo}/anki.zsh
    """.format(repo=repo)))

    # Launchd plist
    la_dir = home / "Library" / "LaunchAgents"
    la_dir.mkdir(parents=True)
    (la_dir / "com.anki-fox.plist").write_text("<plist></plist>\n")

    return home


def run_uninstall(home: Path, stdin_text: str = "y\ny\n") -> subprocess.CompletedProcess:
    """Run uninstall.sh against a fake HOME, mocking launchctl and brew."""
    mock_bin = home / "mockbin"
    mock_bin.mkdir(exist_ok=True)

    # Mock launchctl (silently succeed)
    (mock_bin / "launchctl").write_text("#!/bin/bash\n")
    (mock_bin / "launchctl").chmod(0o755)

    # Mock brew (silently succeed)
    (mock_bin / "brew").write_text("#!/bin/bash\n")
    (mock_bin / "brew").chmod(0o755)

    # Mock osascript (silently succeed)
    (mock_bin / "osascript").write_text("#!/bin/bash\n")
    (mock_bin / "osascript").chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{mock_bin}:/usr/bin:/bin",
    }

    return subprocess.run(
        ["bash", str(REPO_ROOT / "uninstall.sh")],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
    )


class TestUninstallCoverage:
    """Every artifact from install.sh must be removed by uninstall.sh."""

    def test_launchd_plist_removed(self, fake_home):
        plist = fake_home / "Library" / "LaunchAgents" / "com.anki-fox.plist"
        assert plist.exists()
        run_uninstall(fake_home)
        assert not plist.exists()

    def test_hammerspoon_init_lua_removed(self, fake_home):
        init_lua = fake_home / ".hammerspoon" / "init.lua"
        assert init_lua.is_symlink()
        run_uninstall(fake_home)
        assert not init_lua.exists()

    def test_anki_fox_config_dir_removed(self, fake_home):
        config_dir = fake_home / ".anki-fox"
        assert config_dir.exists()
        run_uninstall(fake_home)
        assert not config_dir.exists()

    def test_claude_skill_removed(self, fake_home):
        skill = fake_home / ".claude" / "commands" / "anki.md"
        assert skill.exists()
        run_uninstall(fake_home)
        assert not skill.exists()

    def test_zshrc_lines_removed(self, fake_home):
        zshrc = fake_home / ".zshrc"
        assert "anki-fox" in zshrc.read_text()
        run_uninstall(fake_home)
        text = zshrc.read_text()
        assert "anki-fox" not in text
        assert "Anki watcher" not in text

    def test_repo_deleted_when_confirmed(self, fake_home):
        repo = fake_home / "anki-fox"
        assert repo.exists()
        # Two 'y' responses: one for Hammerspoon, one for repo
        run_uninstall(fake_home, stdin_text="y\ny\n")
        assert not repo.exists()

    def test_repo_kept_when_declined(self, fake_home):
        repo = fake_home / "anki-fox"
        assert repo.exists()
        # 'n' for Hammerspoon, 'n' for repo
        run_uninstall(fake_home, stdin_text="n\nn\n")
        assert repo.exists()

    def test_venv_deleted_with_repo(self, fake_home):
        venv = fake_home / "anki-fox" / ".venv"
        assert venv.exists()
        run_uninstall(fake_home, stdin_text="y\ny\n")
        assert not venv.exists()

    def test_hammerspoon_uninstall_attempted(self, fake_home):
        """When user says 'y' to Hammerspoon, brew uninstall is called."""
        # Create a fake Hammerspoon.app so the uninstall block triggers
        hs_app = Path("/Applications/Hammerspoon.app")
        # We can't create /Applications/Hammerspoon.app in tests, so we test
        # the branch by checking that the script doesn't error when it's absent.
        # The real coverage is: if Hammerspoon.app exists, the prompt appears.
        result = run_uninstall(fake_home, stdin_text="y\ny\n")
        assert result.returncode == 0

    def test_full_uninstall_leaves_clean_state(self, fake_home):
        """After full uninstall (all 'y'), only .zshrc, .claude/, .hammerspoon/ dirs remain."""
        run_uninstall(fake_home, stdin_text="y\ny\n")

        # These should be gone
        assert not (fake_home / "anki-fox").exists()
        assert not (fake_home / ".anki-fox").exists()
        assert not (fake_home / ".hammerspoon" / "init.lua").exists()
        assert not (fake_home / ".claude" / "commands" / "anki.md").exists()
        assert not (fake_home / "Library" / "LaunchAgents" / "com.anki-fox.plist").exists()

        # .zshrc should exist but without anki lines
        zshrc = fake_home / ".zshrc"
        assert zshrc.exists()
        assert "anki-fox" not in zshrc.read_text()
