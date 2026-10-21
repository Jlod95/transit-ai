import hashlib
import json
from datetime import UTC, date, datetime

import pytest
from conftest import zip_mini_feed

from src import agent
from src.summaries import build_summary, design_day, load_summary, service_day_for, write_summary

BUILT_AT = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def summary(mini_feed):
    return build_summary(mini_feed, "mini", git_commit="abc1234", now=BUILT_AT)


def test_one_service_day_with_both_blocks(summary):
    # The mini feed has one service, WEEKDAY (Mon-Fri, all of 2026), removed on Mon 12 Oct.
    # 2026 has 261 weekdays, so 260 dates share the one service pattern.
    days = summary["service_days"]
    assert len(days) == 1
    day = days[0]
    assert day["service_ids"] == ["WEEKDAY"]
    assert len(day["dates"]) == 260
    assert day["dates"][0] == "2026-01-01"  # a Thursday
    assert day["dates"][-1] == "2026-12-31"
    assert "2026-10-12" not in day["dates"]  # the calendar_dates exception
    assert "2026-10-17" not in day["dates"]  # a Saturday
    # Distances and durations, not pass/fail. Ferry block C is not a bus, so it's absent.
    assert day["blocks"] == {
        "A": {"km": 25.0, "minutes": 100.0},
        "B": {"km": 30.0, "minutes": 105.0},
    }


def test_stamp(summary, mini_feed):
    stamp = summary["stamp"]
    assert stamp["agency"] == "mini"
    assert stamp["feed_file"] == "mini_feed.zip"
    assert stamp["feed_sha256"] == hashlib.sha256(mini_feed.read_bytes()).hexdigest()
    assert stamp["feed_version"] is None  # the mini feed has no feed_info.txt
    assert stamp["calendar_start"] == "2026-01-01"
    assert stamp["calendar_end"] == "2026-12-31"
    assert stamp["built_at"] == "2026-10-21T12:00:00Z"
    assert stamp["git_commit"] == "abc1234"


def test_hash_changes_when_the_data_changes_even_if_the_label_does_not(tmp_path, summary):
    # Same feed with one trip 2 km longer, and still no version label: the hash must differ.
    def lengthen_t1(name, rows):
        if name == "stop_times.txt":
            for row in rows:
                if row["trip_id"] == "T1" and row["shape_dist_traveled"] == "10":
                    row["shape_dist_traveled"] = "12"
        return rows

    changed = build_summary(zip_mini_feed(tmp_path / "changed.zip", lengthen_t1), "mini")
    assert changed["stamp"]["feed_version"] == summary["stamp"]["feed_version"]
    assert changed["stamp"]["feed_sha256"] != summary["stamp"]["feed_sha256"]
    assert changed["service_days"][0]["blocks"]["A"]["km"] == 27.0


def test_write_load_and_lookup(tmp_path, summary):
    path = write_summary(summary, tmp_path)
    assert path.name == "mini.json"
    loaded = load_summary(path)
    assert service_day_for(loaded, date(2026, 10, 14))["blocks"]["A"]["km"] == 25.0
    assert service_day_for(loaded, date(2026, 10, 12)) is None
    assert load_summary(tmp_path / "missing.json") is None


def test_design_day_rule():
    summary = {
        "service_days": [
            {"dates": ["2026-10-12"], "blocks": {"a": {"km": 120}, "b": {"km": 50}}},  # Mon
            {"dates": ["2026-10-17"], "blocks": {"c": {"km": 150}, "d": {"km": 80}, "e": {"km": 20}}},
            {"dates": ["2026-10-18"], "blocks": {"f": {"km": 95}, "g": {"km": 95}}},  # Sun
        ]
    }
    # Rule 1, most blocks over range. At 90 km: Mon 1 over (120), Sat 1 over (150),
    # Sun 2 over (95, 95). Sunday wins even though Saturday has more blocks in service.
    group, over = design_day(summary, range_km=90)
    assert group["dates"] == ["2026-10-18"] and over == 2
    # Rule 2, tie-break on blocks in service. At 100 km: Mon 1 over, Sat 1 over, Sun 0.
    # Mon and Sat tie, and Saturday has 3 blocks in service against Monday's 2.
    group, over = design_day(summary, range_km=100)
    assert group["dates"] == ["2026-10-17"] and over == 1
    # Rule 3, full tie goes to the earliest date. At 200 km nothing is over; Saturday has the
    # most blocks. Give Monday a third block too and they tie on both counts: Monday is earlier.
    summary["service_days"][0]["blocks"]["h"] = {"km": 10}
    group, over = design_day(summary, range_km=200)
    assert group["dates"] == ["2026-10-12"] and over == 0


@pytest.fixture
def agent_using_summary(monkeypatch, tmp_path, summary):
    """Point the agent at a built mini summary and at a feed path that doesn't exist, so any
    result can only have come from the summary."""
    monkeypatch.setattr(agent, "SUMMARY_FILE", write_summary(summary, tmp_path))
    monkeypatch.setattr(agent, "HALIFAX_FEED", tmp_path / "no_such_feed.zip")
    return agent


def test_tools_read_the_summary(agent_using_summary):
    run = agent_using_summary.run_tool
    assert run("get_block_distance", {"block_id": "A", "date": "2026-10-14"}) == (
        "Block A drives 25.0 revenue km on 2026-10-14.", False)
    assert run("get_block_duration", {"block_id": "B", "date": "2026-10-14"}) == (
        "Block B is in service for 1 h 45 min on 2026-10-14.", False)
    assert run("get_block_distance", {"block_id": "A", "date": "2026-10-17"})[0] == (
        "No Halifax Transit bus service runs on 2026-10-17.")
    assert "outside the timetable" in run(
        "get_block_distance", {"block_id": "A", "date": "2027-01-05"})[0]

    fleet = json.loads(run("get_fleet_feasibility", {"date": "2026-10-14", "season": "winter"})[0])
    assert fleet["total_blocks"] == 2 and fleet["within_range"] == 2  # range 180 km
    assert fleet["data_snapshot"]["timetable_covers"] == "2026-01-01 to 2026-12-31"

    design = json.loads(run("get_design_day", {"season": "winter"})[0])
    assert design["design_day"] == "2026-01-01"
    assert design["same_pattern_dates"] == 260
    assert design["blocks_over_range"] == 0


def test_summary_alone_is_enough_data(agent_using_summary):
    # The deployed container has a summary but no raw feed: that must be accepted.
    assert not agent_using_summary.HALIFAX_FEED.exists()
    agent_using_summary.check_block_data()  # raises if not


def test_no_summary_and_no_feed_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "SUMMARY_FILE", tmp_path / "no_summary.json")
    monkeypatch.setattr(agent, "HALIFAX_FEED", tmp_path / "no_feed.zip")
    with pytest.raises(agent.AgentError, match="No block data"):
        agent.check_block_data()
