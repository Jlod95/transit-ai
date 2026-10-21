import zipfile

import pytest

from src.estimates import (
    TURNAROUND_SECONDS,
    chain_trips,
    haversine_km,
    road_factor_from,
    shape_lengths_km,
    straight_line_km,
)


def test_shape_length_converted_from_metres(tmp_path):
    # Dublin-style shapes.txt: shape_dist_traveled in metres. The trip's length is the largest
    # value, 3,200 m, which must come out as 3.2 km (not 3,200 km).
    path = tmp_path / "shapes.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "shapes.txt",
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
            "S1,53.3500,-6.2600,1,0\n"
            "S1,53.3600,-6.2600,2,1500\n"
            "S1,53.3700,-6.2600,3,3200\n",
        )
    with zipfile.ZipFile(path) as zf:
        assert shape_lengths_km(zf) == {"S1": pytest.approx(3.2)}


def test_straight_line_between_stops():
    # Three stops 0.01 degrees of latitude apart, due north: each step is 1.112 km on a
    # 6,371 km Earth (2 * pi * 6371 / 360 * 0.01), so two steps are 2.224 km.
    stops = [(53.35, -6.26), (53.36, -6.26), (53.37, -6.26)]
    assert haversine_km(stops[0], stops[1]) == pytest.approx(1.112, abs=0.001)
    assert straight_line_km(stops) == pytest.approx(2.224, abs=0.001)
    # With a road factor of 1.25, the estimate is 2.224 x 1.25 = 2.780 km.
    assert straight_line_km(stops) * 1.25 == pytest.approx(2.780, abs=0.001)


def test_road_factor_is_total_exact_over_total_straight():
    # 12 + 18 = 30 km by road against 10 + 14 = 24 km in straight lines: 30 / 24 = 1.25.
    # The 0.3 km trip is too short to measure reliably and is ignored.
    assert road_factor_from([12, 18, 1], [10, 14, 0.3]) == pytest.approx(1.25)


def minutes(hhmm):
    hours, mins = hhmm.split(":")
    return int(hours) * 3600 + int(mins) * 60


def test_trip_chaining_on_a_tiny_route():
    # One route between terminals A and B. A bus can take a trip leaving its terminal
    # at least 5 minutes after it arrived there; otherwise a new bus starts.
    assert TURNAROUND_SECONDS == 300
    trips = [
        ("T1", "A", "B", minutes("06:00"), minutes("06:30")),  # bus 1
        ("T2", "B", "A", minutes("06:33"), minutes("07:00")),  # bus 1 has waited 3 min only: bus 2
        ("T3", "B", "A", minutes("06:40"), minutes("07:10")),  # bus 1 has waited 10 min: bus 1
        ("T4", "A", "B", minutes("07:05"), minutes("07:35")),  # bus 2 arrived A 07:00, exactly 5 min: bus 2
        ("T5", "A", "B", minutes("07:12"), minutes("07:40")),  # bus 1 arrived A 07:10, 2 min: bus 3
    ]
    assert chain_trips(trips) == [["T1", "T3"], ["T2", "T4"], ["T5"]]


def test_chaining_prefers_the_bus_that_has_waited_longest():
    # Two buses wait at A (arrived 06:30 and 06:50); the 07:00 trip goes to the 06:30 one.
    trips = [
        ("X", "B", "A", minutes("06:00"), minutes("06:30")),
        ("Y", "B", "A", minutes("06:20"), minutes("06:50")),
        ("Z", "A", "B", minutes("07:00"), minutes("07:30")),
    ]
    assert chain_trips(trips) == [["X", "Z"], ["Y"]]
