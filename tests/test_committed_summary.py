"""Checks on the committed summaries, which are what the deployed app answers from.

These run in CI, which has no raw feeds, so every agency's committed numbers are checked on
every push.
"""

from datetime import date
from pathlib import Path

import pytest

from src.agencies import AGENCIES
from src.summaries import file_sha256, load_summary, service_day_for

ROOT = Path(__file__).parent.parent
SUMMARIES = ROOT / "data" / "summaries"


def summary_of(key):
    loaded = load_summary(SUMMARIES / f"{key}.json")
    assert loaded is not None, f"{key}.json is missing; build it with scripts/build_summaries.py {key}"
    return loaded


@pytest.mark.parametrize("key", sorted(AGENCIES))
def test_stamp_is_complete_and_from_committed_code(key):
    stamp = summary_of(key)["stamp"]
    assert stamp["agency"] == key
    assert len(stamp["feeds"]) == len(AGENCIES[key].feeds)
    assert all(len(f["sha256"]) == 64 for f in stamp["feeds"])
    assert stamp["calendar_start"] <= stamp["calendar_end"]
    assert stamp["distance_method"] and stamp["block_method"]
    # Built from committed code, so the commit in the stamp identifies the exact code used.
    assert stamp["git_commit"] != "unknown"
    assert not stamp["git_commit"].endswith("-dirty")


def test_london_is_labelled_estimated_and_inferred():
    stamp = summary_of("london")["stamp"]
    assert stamp["distance_method"].startswith("ESTIMATED")
    assert stamp["block_method"].startswith("INFERRED")
    assert 1.0 < stamp["road_factor"] < 2.0
    assert stamp["road_factor_calibration"]["trips_used"] > 1000


def test_known_halifax_block():
    # Block 722145 on Wed 14 Oct 2026: 80.5 km, from 5:32 to 8:48 = 196 minutes.
    block = service_day_for(summary_of("halifax"), date(2026, 10, 14))["blocks"]["722145"]
    assert block["km"] == pytest.approx(80.5, abs=0.1)
    assert block["minutes"] == 196.0


@pytest.mark.parametrize("key", sorted(AGENCIES))
def test_summary_matches_the_local_feeds(key):
    # Locally, if a raw feed has changed since the summary was built, the summary is stale.
    feeds = [ROOT / f for f in AGENCIES[key].feeds]
    if not all(f.exists() for f in feeds):
        pytest.skip("no local raw feeds to compare against")
    built_from = [f["sha256"] for f in summary_of(key)["stamp"]["feeds"]]
    assert built_from == [file_sha256(f) for f in feeds], (
        f"a raw feed for {key} differs from the one its summary was built from; rebuild with "
        f"scripts/build_summaries.py {key}"
    )
