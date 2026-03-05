"""Tests proving PIP_REQUIRE_VIRTUALENV breaks bare pip and venv fixes it."""

import os
import subprocess
import sys
import venv

import pytest


@pytest.fixture
def tmp_venv(tmp_path):
    """Create a temporary virtualenv and return its path."""
    venv_dir = tmp_path / ".venv"
    venv.create(venv_dir, with_pip=True)
    return venv_dir


class TestInstallVenv:
    def test_bare_pip_fails_with_require_virtualenv(self, tmp_path):
        """Bare pip3 install fails when PIP_REQUIRE_VIRTUALENV=1 (reproduces the bug)."""
        env = {**os.environ, "PIP_REQUIRE_VIRTUALENV": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "flask"],
            capture_output=True,
            env=env,
        )
        assert result.returncode != 0

    def test_venv_pip_succeeds_with_require_virtualenv(self, tmp_venv):
        """Venv pip succeeds even with PIP_REQUIRE_VIRTUALENV=1 (proves the fix)."""
        env = {**os.environ, "PIP_REQUIRE_VIRTUALENV": "1"}
        pip = str(tmp_venv / "bin" / "pip")
        result = subprocess.run(
            [pip, "install", "--dry-run", "flask"],
            capture_output=True,
            env=env,
        )
        assert result.returncode == 0

    def test_venv_python_can_import_deps(self, tmp_venv):
        """Packages installed in the venv are importable by the venv python."""
        pip = str(tmp_venv / "bin" / "pip")
        python = str(tmp_venv / "bin" / "python")

        subprocess.check_call(
            [pip, "install", "-q", "flask"],
            env={**os.environ, "PIP_REQUIRE_VIRTUALENV": "1"},
        )

        result = subprocess.run(
            [python, "-c", "import flask"],
            capture_output=True,
        )
        assert result.returncode == 0
