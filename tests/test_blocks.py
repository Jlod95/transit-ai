from datetime import date
from pathlib import Path

import pytest

from src.blocks import daily_block_distance

HALIFAX_FEED = Path(__file__).parent.parent / "data" / "raw" / "halifax.zip"

# The feed is gitignored, so it isn't available in CI; skip there instead of failing.
needs_halifax = pytest.mark.skipif(not HALIFAX_FEED.exists(), reason="data/raw/halifax.zip missing")


@needs_halifax
def test_block_722145_on_a_weekday():
    distances = daily_block_distance(HALIFAX_FEED, date(2026, 10, 14))
    assert distances["722145"] == pytest.approx(80.5, abs=0.1)
