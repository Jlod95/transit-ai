"""Which code built a file: shared by the build scripts that stamp their outputs."""

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
# Built outputs: rebuilding them doesn't make the code "dirty".
OUTPUT_DIRS = ("data/summaries", "data/index")


def current_git_commit():
    """The short commit hash, "-dirty" if tracked code has uncommitted changes.

    GIT_COMMIT in the environment wins (for builds without a .git folder); "unknown" if git
    isn't available.
    """
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    try:
        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()

        commit = git("rev-parse", "--short", "HEAD")
        excluded = [f":(exclude){d}" for d in OUTPUT_DIRS]
        changed = git("status", "--porcelain", "--untracked-files=no", "--", ".", *excluded)
        return commit + ("-dirty" if changed else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
