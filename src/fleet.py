"""Crude fleet, charging, cost and CO2 figures for one agency and season.

Store facts, compute judgement: the summary holds each block's km and start/end times; these
functions turn them into judgements at question time, using the design day and the
assumptions in config/assumptions.py, each reported next to its source or placeholder label.
Any setting can be overridden by keyword (tests do).
"""

import math

from config import assumptions
from src.feasibility import range_km_for
from src.summaries import design_day

RANGE_SETTINGS = ("nominal_battery_kwh", "usable_fraction", "kwh_per_km")


def _setting(name, overrides):
    return overrides[name] if name in overrides else getattr(assumptions, name)


def _with_sources(used, values):
    """The range assumptions plus extra values, with every value's source alongside."""
    return {
        **{k: v for k, v in used.items() if k != "sources"},
        **values,
        "sources": {**used["sources"], **assumptions.sources_for(*values)},
    }


def peak_blocks_in_service(blocks):
    """The most blocks running at the same moment: the number of buses the day needs.

    A block ending at the exact second another starts doesn't overlap it (one bus could not
    do both, but neither are two needed at that instant).
    """
    events = sorted(
        [(b["start"], 1) for b in blocks.values()] + [(b["end"], -1) for b in blocks.values()]
    )  # at equal times -1 sorts before +1, so an end is counted before a start
    running = peak = 0
    for _, step in events:
        running += step
        peak = max(peak, running)
    return peak


def _design_day(summary, season, overrides):
    range_km, used = range_km_for(season, **{k: overrides[k] for k in RANGE_SETTINGS if k in overrides})
    group, over = design_day(summary, range_km)
    if group is None:
        raise ValueError("The summary contains no bus service.")
    return group, over, range_km, used


def fleet_size(summary, season, **overrides):
    """Buses needed on the design day today and if electric, and their ratio."""
    group, over, range_km, used = _design_day(summary, season, overrides)
    today = peak_blocks_in_service(group["blocks"])
    electric = today + over
    return {
        "design_day": group["dates"][0],
        "season": season,
        "range_km": round(range_km, 1),
        "blocks_in_service": len(group["blocks"]),
        "buses_needed_today": today,
        "blocks_over_range": over,
        "electric_buses_needed": electric,
        "replacement_ratio": round(electric / today, 3) if today else None,
        "benchmark_ratio": _setting("replacement_ratio_benchmark", overrides),
        "method": (
            "Buses today = the most blocks in service at the same moment on the design day. "
            "Each block over one charge's range needs one extra bus (crude: assumes a fresh bus "
            "swaps in mid-day). Ratio = electric buses / buses today. Spare buses not included."
        ),
        "assumptions": _with_sources(
            used, {"replacement_ratio_benchmark": _setting("replacement_ratio_benchmark", overrides)}
        ),
    }


def charging_needs(summary, season, **overrides):
    """Overnight energy for the design day and the depot power to deliver it in the window."""
    group, _, _, used = _design_day(summary, season, overrides)
    kwh_per_km = used["kwh_per_km"]
    window = _setting("charging_window_hours", overrides)
    daily_km = sum(b["km"] for b in group["blocks"].values())
    energy_kwh = daily_km * kwh_per_km
    return {
        "design_day": group["dates"][0],
        "season": season,
        "blocks_in_service": len(group["blocks"]),
        "daily_km": round(daily_km, 1),
        "overnight_energy_kwh": round(energy_kwh, 1),
        "overnight_energy_mwh": round(energy_kwh / 1000, 2),
        "charging_window_hours": window,
        "peak_depot_power_kw": round(energy_kwh / window, 1),
        "peak_depot_power_mw": round(energy_kwh / window / 1000, 2),
        "method": (
            "Energy = sum of block km on the design day x kWh per km. Peak power = that energy "
            "spread evenly over the charging window, with every bus charging at once. Blocks "
            "over range would need more than one battery's worth; this counts their full energy. "
            "Revenue km only, so real energy is higher."
        ),
        "assumptions": _with_sources(used, {"charging_window_hours": window}),
    }


def cost_and_co2(summary, season, **overrides):
    """Crude capital cost, annual energy cost electric vs diesel, and annual CO2 saved."""
    fleet = fleet_size(summary, season, **overrides)
    charging = charging_needs(summary, season, **overrides)
    s = {name: _setting(name, overrides) for name in (
        "buses_per_charger", "currency", "electric_bus_price", "charger_price",
        "electricity_price_per_kwh", "diesel_price_per_litre", "diesel_litres_per_km",
        "kg_co2_per_litre_diesel", "annual_service_days",
    )}
    _, _, _, used = _design_day(summary, season, overrides)
    kwh_per_km = used["kwh_per_km"]

    # Every electric bus needed (replacements plus extras) is priced, with its chargers.
    electric_buses = fleet["electric_buses_needed"]
    extra_buses = fleet["blocks_over_range"]
    chargers = math.ceil(electric_buses / s["buses_per_charger"])
    capital = electric_buses * s["electric_bus_price"] + chargers * s["charger_price"]

    annual_km = charging["daily_km"] * s["annual_service_days"]
    electricity_cost = annual_km * kwh_per_km * s["electricity_price_per_kwh"]
    diesel_litres = annual_km * s["diesel_litres_per_km"]
    diesel_cost = diesel_litres * s["diesel_price_per_litre"]
    co2_tonnes = diesel_litres * s["kg_co2_per_litre_diesel"] / 1000

    return {
        "design_day": fleet["design_day"],
        "season": season,
        "currency": s["currency"],
        "electric_buses_priced": electric_buses,
        "of_which_extra_buses": extra_buses,
        "chargers": chargers,
        "capital_cost": round(capital),
        "annual_km": round(annual_km),
        "annual_electricity_cost": round(electricity_cost),
        "annual_diesel_cost": round(diesel_cost),
        "annual_energy_saving": round(diesel_cost - electricity_cost),
        "annual_co2_saved_tonnes": round(co2_tonnes, 1),
        "method": (
            "Capital = every electric bus needed (replacements for today's buses plus one "
            "extra per block over range) x electric bus price + chargers (electric buses / buses "
            "per charger, rounded up) x charger price. With the Halifax all-in price the charger "
            "is inside the bus price, so the charger price is 0. Grid upgrades and spare buses are "
            "not included. Annual km = design-day km x "
            "annual service days. Energy costs use this season's kWh per km all year. CO2 "
            "saved = diesel litres x kg CO2 per litre; electricity generation emissions are "
            "not subtracted."
        ),
        "assumptions": _with_sources(used, {**s, "electric_bus_price": round(s["electric_bus_price"])}),
    }
