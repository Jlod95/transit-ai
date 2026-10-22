from datetime import date

import pytest

from src.feasibility import fleet_feasibility

WEEKDAY = date(2026, 10, 14)


def test_one_block_fits_one_does_not(mini_feed):
    # Usable = 100 kWh x 0.5 = 50 kWh. Range = 50 kWh / 2.0 kWh per km = 25 km.
    # Block A is 25 km (fits, exactly at the limit); block B is 30 km (too far).
    result = fleet_feasibility(
        mini_feed,
        WEEKDAY,
        "winter",
        nominal_battery_kwh=100,
        usable_fraction=0.5,
        kwh_per_km={"winter": 2.0},
    )
    assert result["assumptions"]["usable_kwh"] == 50.0
    assert result["range_km"] == 25.0
    assert result["total_blocks"] == 2
    assert result["within_range"] == 1
    assert result["exceeding_range"] == 1
    assert result["pct_within_range"] == 50.0
    assert result["longest_blocks"] == [
        {"block_id": "B", "km": 30.0},
        {"block_id": "A", "km": 25.0},
    ]


def test_usable_kwh_is_nominal_times_usable_fraction(mini_feed):
    # Config (TTC New Flyer, p. 55): 400 kWh nominal x 285/400 usable = 285 kWh.
    result = fleet_feasibility(mini_feed, WEEKDAY, "winter")
    assumptions = result["assumptions"]
    assert assumptions["nominal_battery_kwh"] == 400
    assert assumptions["usable_fraction"] == 0.7125
    assert assumptions["usable_kwh"] == 285.0
    assert assumptions["sources"]["usable_fraction"]["pages"] == "55"


def test_uses_config_assumptions_by_default(mini_feed):
    # Config: winter kWh/km = 1.22 x 1.425 = 1.7385; 285 usable kWh / 1.7385 = 163.9 km,
    # so both blocks (25 and 30 km) fit.
    result = fleet_feasibility(mini_feed, WEEKDAY, "winter")
    assert result["assumptions"]["kwh_per_km"] == 1.7385
    assert result["range_km"] == 163.9
    assert result["within_range"] == 2


def test_unknown_season_is_rejected(mini_feed):
    with pytest.raises(ValueError):
        fleet_feasibility(mini_feed, WEEKDAY, "spring")
