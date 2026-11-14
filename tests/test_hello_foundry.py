"""experiments/foundry/hello_foundry.py stops with a clear message when its settings are missing.

Checks the settings only: no Azure packages, sign-in or network needed.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "experiments" / "foundry" / "hello_foundry.py"
spec = importlib.util.spec_from_file_location("hello_foundry", SCRIPT)
hello_foundry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hello_foundry)

BOTH = {"FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/demo",
        "FOUNDRY_MODEL": "my-deployment"}


@pytest.mark.parametrize("missing", ["FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL"])
def test_each_missing_variable_is_named(missing):
    env = {k: v for k, v in BOTH.items() if k != missing}
    with pytest.raises(SystemExit, match=f"Missing {missing}"):
        hello_foundry.read_settings(env)


def test_both_missing_or_blank_are_named():
    with pytest.raises(SystemExit, match="Missing FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL"):
        hello_foundry.read_settings({"FOUNDRY_MODEL": "  "})


def test_settings_are_read_when_present():
    assert hello_foundry.read_settings(BOTH) == BOTH
