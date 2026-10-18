import zipfile
from datetime import date
from pathlib import Path

import pytest

from src.feasibility import fleet_feasibility

MINI_FEED_DIR = Path(__file__).parent / "fixtures" / "mini_feed"
WEEKDAY = date(2026, 10, 14)


@pytest.fixture
def mini_feed(tmp_path):
    zip_path = tmp_path / "mini_feed.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for txt in MINI_FEED_DIR.glob("*.txt"):
            zf.write(txt, arcname=txt.name)
    return zip_path


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
    # Config: 450 kWh nominal x 0.8 usable = 360 kWh.
    result = fleet_feasibility(mini_feed, WEEKDAY, "winter")
    assumptions = result["assumptions"]
    assert assumptions["nominal_battery_kwh"] == 450
    assert assumptions["usable_fraction"] == 0.8
    assert assumptions["usable_kwh"] == 360.0


def test_uses_config_assumptions_by_default(mini_feed):
    # Config: 360 usable kWh / 2.0 kWh per km in winter = 180 km, so both blocks fit.
    result = fleet_feasibility(mini_feed, WEEKDAY, "winter")
    assert result["range_km"] == 180.0
    assert result["within_range"] == 2


def test_unknown_season_is_rejected(mini_feed):
    with pytest.raises(ValueError):
        fleet_feasibility(mini_feed, WEEKDAY, "spring")
