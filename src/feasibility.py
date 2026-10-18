"""Crude fleet-level check: which blocks fit within one battery charge.

Compares each block's daily revenue km with the range of a fully charged bus. Assumes one
overnight charge and no charging during the day. Deadhead is not in GTFS, so real daily
distance is higher than the figures used here and the result is optimistic.
"""

from datetime import date

from config import assumptions
from src.blocks import daily_block_distance


def fleet_feasibility(
    feed_path,
    service_date: date,
    season: str,
    nominal_battery_kwh: float | None = None,
    usable_fraction: float | None = None,
    kwh_per_km: dict[str, float] | None = None,
) -> dict:
    """Return a summary of how many bus blocks on service_date fit within one charge.

    Battery size, usable fraction and consumption come from config/assumptions.py unless
    passed in.
    """
    if nominal_battery_kwh is None:
        nominal_battery_kwh = assumptions.nominal_battery_kwh
    if usable_fraction is None:
        usable_fraction = assumptions.usable_fraction
    if kwh_per_km is None:
        kwh_per_km = assumptions.kwh_per_km
    if season not in kwh_per_km:
        raise ValueError(f"Unknown season {season!r}; expected one of {sorted(kwh_per_km)}")

    usable_kwh = nominal_battery_kwh * usable_fraction
    range_km = usable_kwh / kwh_per_km[season]
    distances = daily_block_distance(feed_path, service_date)

    total = len(distances)
    within = sum(1 for km in distances.values() if km <= range_km)
    longest = sorted(distances.items(), key=lambda item: item[1], reverse=True)[:5]

    return {
        "service_date": service_date.isoformat(),
        "season": season,
        "range_km": round(range_km, 1),
        "total_blocks": total,
        "within_range": within,
        "exceeding_range": total - within,
        "pct_within_range": round(100 * within / total, 1) if total else 0.0,
        "longest_blocks": [{"block_id": b, "km": round(km, 1)} for b, km in longest],
        "assumptions": {
            "nominal_battery_kwh": nominal_battery_kwh,
            "usable_fraction": usable_fraction,
            "usable_kwh": round(usable_kwh, 1),
            "usable_fraction_reason": (
                "Industry practice: buses keep about 20% in reserve, because routinely "
                "discharging below that speeds up battery wear and leaves no margin for "
                "delays and cold."
            ),
            "kwh_per_km": kwh_per_km[season],
            "status": "Battery size and kWh/km are PLACEHOLDER values, to be sourced in M4",
            "notes": "One overnight charge, no daytime charging; revenue km only (no deadhead).",
        },
    }
