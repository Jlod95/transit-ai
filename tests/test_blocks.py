import zipfile
from datetime import date
from pathlib import Path

import pytest

from src.blocks import daily_block_distance

HALIFAX_FEED = Path(__file__).parent.parent / "data" / "raw" / "halifax.zip"
MINI_FEED_DIR = Path(__file__).parent / "fixtures" / "mini_feed"

# The feed is gitignored, so it isn't available in CI; skip there instead of failing.
needs_halifax = pytest.mark.skipif(not HALIFAX_FEED.exists(), reason="data/raw/halifax.zip missing")


@pytest.fixture
def mini_feed(tmp_path):
    """Zip the hand-made fixture feed into pytest's temporary folder and return the zip path."""
    zip_path = tmp_path / "mini_feed.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for txt in MINI_FEED_DIR.glob("*.txt"):
            zf.write(txt, arcname=txt.name)
    return zip_path


def test_mini_feed_weekday_totals(mini_feed):
    # Block A: T1 10 + T2 10 + T3 5 = 25 km. Block B: T4 15 + T5 15 = 30 km.
    distances = daily_block_distance(mini_feed, date(2026, 10, 14))  # Wednesday
    assert distances == pytest.approx({"A": 25.0, "B": 30.0})


def test_mini_feed_excludes_ferry(mini_feed):
    # Block C is the ferry trip FT1 (route_type 4) and runs on the same weekday service.
    distances = daily_block_distance(mini_feed, date(2026, 10, 14))
    assert "C" not in distances


def test_mini_feed_exception_date_has_no_blocks(mini_feed):
    # calendar_dates.txt removes the WEEKDAY service on Monday 12 Oct 2026.
    assert daily_block_distance(mini_feed, date(2026, 10, 12)) == {}


@needs_halifax
def test_block_722145_on_a_weekday():
    distances = daily_block_distance(HALIFAX_FEED, date(2026, 10, 14))
    assert distances["722145"] == pytest.approx(80.5, abs=0.1)
