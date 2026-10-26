from datetime import date
from pathlib import Path

import pytest
from conftest import zip_mini_feed

from src.blocks import (
    BlockCoverageError,
    MissingDistanceError,
    TripSpeedError,
    daily_block_distance,
    daily_block_duration,
    gtfs_time_to_seconds,
    trip_speed_problems,
)
from src.summaries import build_summary

HALIFAX_FEED = Path(__file__).parent.parent / "data" / "raw" / "halifax.zip"

# The feed is gitignored, so it isn't available in CI; skip there instead of failing.
needs_halifax = pytest.mark.skipif(not HALIFAX_FEED.exists(), reason="data/raw/halifax.zip missing")


@pytest.fixture
def mini_feed_missing_t4(tmp_path):
    """The mini feed with every shape_dist_traveled for bus trip T4 (block B) blanked."""

    def blank_t4(name, rows):
        if name == "stop_times.txt":
            for row in rows:
                if row["trip_id"] == "T4":
                    row["shape_dist_traveled"] = ""
        return rows

    return zip_mini_feed(tmp_path / "mini_feed_missing_t4.zip", blank_t4)


@pytest.fixture
def mini_feed_with_rail(tmp_path):
    """The mini feed plus a weekday rail route (route_type 1) whose one trip is block D."""

    def add_rail(name, rows):
        if name == "routes.txt":
            rows.append({"route_id": "RAIL", "agency_id": "MINI", "route_short_name": "L1",
                         "route_long_name": "Test Rail Line", "route_type": "1"})
        if name == "trips.txt":
            rows.append({"route_id": "RAIL", "service_id": "WEEKDAY", "trip_id": "RT1",
                         "block_id": "D"})
        if name == "stop_times.txt":
            rows += [
                {"trip_id": "RT1", "arrival_time": "11:00:00", "departure_time": "11:00:00",
                 "stop_id": "S1", "stop_sequence": "1", "shape_dist_traveled": ""},
                {"trip_id": "RT1", "arrival_time": "11:30:00", "departure_time": "11:30:00",
                 "stop_id": "S3", "stop_sequence": "2", "shape_dist_traveled": "50"},
            ]
        return rows

    return zip_mini_feed(tmp_path / "mini_feed_with_rail.zip", add_rail)


@pytest.fixture
def mini_feed_t5_without_block(tmp_path):
    """The mini feed with bus trip T5's block_id removed: 4 of 5 bus trips keep a block."""

    def drop_block(name, rows):
        if name == "trips.txt":
            for row in rows:
                if row["trip_id"] == "T5":
                    row["block_id"] = ""
        return rows

    return zip_mini_feed(tmp_path / "mini_feed_t5_without_block.zip", drop_block)


def mini_feed_t4_scaled(tmp_path, factor):
    """The mini feed with bus trip T4's shape_dist_traveled values multiplied by factor."""

    def scale_t4(name, rows):
        if name == "stop_times.txt":
            for row in rows:
                if row["trip_id"] == "T4" and row["shape_dist_traveled"]:
                    row["shape_dist_traveled"] = f"{float(row['shape_dist_traveled']) * factor:g}"
        return rows

    return zip_mini_feed(tmp_path / f"mini_feed_t4_x{factor:g}.zip", scale_t4)


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


def test_rail_route_is_not_counted_as_a_bus(mini_feed_with_rail):
    # Block D is a rail trip (route_type 1) on the same weekday service as the buses.
    distances = daily_block_distance(mini_feed_with_rail, date(2026, 10, 14))
    assert distances == pytest.approx({"A": 25.0, "B": 30.0})
    assert "D" not in daily_block_duration(mini_feed_with_rail, date(2026, 10, 14))


def test_low_block_coverage_raises(mini_feed_t5_without_block):
    # 4 of the 5 weekday bus trips have a block_id: 80%, below the 95% minimum. Without the
    # guard, T5's 15 km would silently vanish and block B would read 15 km instead of 30.
    with pytest.raises(BlockCoverageError) as error:
        daily_block_distance(mini_feed_t5_without_block, date(2026, 10, 14))
    assert error.value.with_block == 4
    assert error.value.total == 5
    assert "80.0%" in str(error.value)


def test_trip_without_distances_raises(mini_feed_missing_t4):
    # Counting T4 as 0 km would silently report block B as 15 km instead of 30.
    with pytest.raises(MissingDistanceError) as error:
        daily_block_distance(mini_feed_missing_t4, date(2026, 10, 14))
    assert error.value.missing == {"T4": "B"}
    assert "trip T4 (block B)" in str(error.value)


@needs_halifax
def test_block_722145_on_a_weekday():
    distances = daily_block_distance(HALIFAX_FEED, date(2026, 10, 14))
    assert distances["722145"] == pytest.approx(80.5, abs=0.1)


def test_gtfs_time_past_midnight_is_not_wrapped():
    # 26:01:00 is 2:01am the next morning, still on the same service day.
    assert gtfs_time_to_seconds("26:01:00") == 93_660


def test_mini_feed_block_durations(mini_feed):
    # Block A: T1 departs 06:00, T3 arrives 07:40 = 100 min. Block B: 08:00 to 09:45 = 105 min.
    durations = daily_block_duration(mini_feed, date(2026, 10, 14))
    assert durations == pytest.approx({"A": 100.0, "B": 105.0})


@needs_halifax
def test_block_722145_duration_on_a_weekday():
    # First departure 5:32, last arrival 8:48.
    durations = daily_block_duration(HALIFAX_FEED, date(2026, 10, 14))
    assert durations["722145"] == pytest.approx(196)


# --- Speed guard: km / scheduled hours must be plausible for a bus trip ---


def test_normal_trip_speed_passes(mini_feed):
    # T4 drives 15 km in 45 min = 20 km/h, inside 3-70 km/h, as does every mini-feed bus trip.
    assert trip_speed_problems({"T4": "B"}, {"T4": 15.0}, {"T4": 8 * 3600}, {"T4": 8 * 3600 + 45 * 60}) == {}
    assert daily_block_distance(mini_feed, date(2026, 10, 14)) == pytest.approx({"A": 25.0, "B": 30.0})


def test_zero_km_trip_stops_the_build(tmp_path):
    # Without the guard, T4 would count as 0 km and block B would silently read 15 km, not 30.
    feed = mini_feed_t4_scaled(tmp_path, 0)
    with pytest.raises(TripSpeedError) as error:
        daily_block_distance(feed, date(2026, 10, 14))
    assert error.value.problems == {"T4": {"block": "B", "km": 0.0, "minutes": 45.0, "kmh": 0.0}}
    assert "trip T4 (block B: 0 km in 45 min = 0.0 km/h)" in str(error.value)
    with pytest.raises(TripSpeedError):
        build_summary(feed, "mini")  # the summary build stops too


def test_distance_1000_times_too_large_stops_the_build(tmp_path):
    # Metres read as km: 15,000 "km" in 45 min = 20,000 km/h.
    with pytest.raises(TripSpeedError) as error:
        daily_block_distance(mini_feed_t4_scaled(tmp_path, 1000), date(2026, 10, 14))
    assert error.value.problems["T4"]["kmh"] == 20000.0
    assert list(error.value.problems) == ["T4"]


def test_speed_limits_are_settings_and_zero_minutes_is_flagged():
    trip = ({"T": "X"}, {"T": 15.0}, {"T": 0}, {"T": 45 * 60})  # 20 km/h
    assert trip_speed_problems(*trip, min_kmh=25, max_kmh=60)["T"]["kmh"] == 20.0
    assert trip_speed_problems({"T": "X"}, {"T": 5.0}, {"T": 60}, {"T": 60})["T"]["kmh"] is None
