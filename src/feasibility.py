"""Crude fleet-level check: which blocks fit within one battery charge.

Compares each block's daily revenue km with the range of a fully charged bus. Assumes one
overnight charge and no charging during the day. Deadhead is not in GTFS, so real daily
distance is higher than the figures used here and the result is optimistic.
"""

from datetime import date

from config import assumptions
from src.blocks import daily_block_distance


def range_km_for(season, nominal_battery_kwh=None, usable_fraction=None, kwh_per_km=None):
    """Return (range_km, assumptions used) for one season.

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
    sources = assumptions.sources_for("nominal_battery_kwh", "usable_fraction")
    energy = assumptions.ASSUMPTION_SOURCES["kwh_per_km"]
    sources["kwh_per_km"] = {"status": energy["status"], **energy.get(season, {})}
    used = {
        "nominal_battery_kwh": nominal_battery_kwh,
        "usable_fraction": round(usable_fraction, 4),
        "usable_kwh": round(usable_kwh, 1),
        "kwh_per_km": round(kwh_per_km[season], 4),
        "notes": "One overnight charge, no daytime charging; revenue km only (no deadhead).",
        "sources": sources,
    }
    return usable_kwh / kwh_per_km[season], used


def assess_distances(distances: dict[str, float], season: str, **overrides) -> dict:
    """Compare each block's daily km with one charge's range for the season."""
    range_km, used = range_km_for(season, **overrides)
    total = len(distances)
    within = sum(1 for km in distances.values() if km <= range_km)
    longest = sorted(distances.items(), key=lambda item: item[1], reverse=True)[:5]
    return {
        "season": season,
        "range_km": round(range_km, 1),
        "total_blocks": total,
        "within_range": within,
        "exceeding_range": total - within,
        "pct_within_range": round(100 * within / total, 1) if total else 0.0,
        "pct_exceeding_range": round(100 * (total - within) / total, 1) if total else 0.0,
        "longest_blocks": [{"block_id": b, "km": round(km, 1)} for b, km in longest],
        "assumptions": used,
    }


def fleet_feasibility(
    feed_path,
    service_date: date,
    season: str,
    nominal_battery_kwh: float | None = None,
    usable_fraction: float | None = None,
    kwh_per_km: dict[str, float] | None = None,
) -> dict:
    """Return a summary of how many bus blocks on service_date fit within one charge,
    computed directly from the feed.
    """
    # Check the season before the slow feed read, so a bad season fails fast.
    range_km_for(season, nominal_battery_kwh, usable_fraction, kwh_per_km)
    distances = daily_block_distance(feed_path, service_date)
    result = assess_distances(
        distances,
        season,
        nominal_battery_kwh=nominal_battery_kwh,
        usable_fraction=usable_fraction,
        kwh_per_km=kwh_per_km,
    )
    return {"service_date": service_date.isoformat(), **result}
