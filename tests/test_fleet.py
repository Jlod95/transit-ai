"""Fleet, charging, cost and CO2 on the mini feed, with every placeholder passed in explicitly
so the expected numbers can be checked by hand whatever config/assumptions.py says.

Mini feed, every weekday: block A = 25 km, 06:00-07:40; block B = 30 km, 08:00-09:45.
"""

import pytest

from src.fleet import charging_needs, cost_and_co2, fleet_size, peak_blocks_in_service
from src.summaries import build_summary

SETTINGS = {
    "nominal_battery_kwh": 450,
    "usable_fraction": 0.8,  # 360 usable kWh
    "kwh_per_km": {"winter": 2.0, "summer": 1.3},  # winter range 360 / 2.0 = 180 km
    "replacement_ratio_benchmark": 1.2,
    "charging_window_hours": 6,
    "buses_per_charger": 1,
    "currency": "CAD",
    "electric_bus_price": 1_200_000,
    "charger_price": 150_000,
    "electricity_price_per_kwh": 0.15,
    "diesel_price_per_litre": 1.70,
    "diesel_litres_per_km": 0.55,
    "kg_co2_per_litre_diesel": 2.68,
    "annual_service_days": 300,
}
# A tiny battery: 50 x 0.5 = 25 kWh usable, / 1.0 kWh per km = 25 km range. A (25 km) fits
# exactly; B (30 km) is over.
TINY_BATTERY = {**SETTINGS, "nominal_battery_kwh": 50, "usable_fraction": 0.5,
                "kwh_per_km": {"winter": 1.0}}


@pytest.fixture
def summary(mini_feed):
    return build_summary(mini_feed, "mini")


def test_summary_stores_block_start_and_end(summary):
    blocks = summary["service_days"][0]["blocks"]
    assert (blocks["A"]["start"], blocks["A"]["end"]) == (6 * 3600, 7 * 3600 + 40 * 60)
    assert (blocks["B"]["start"], blocks["B"]["end"]) == (8 * 3600, 9 * 3600 + 45 * 60)


def test_peak_blocks_in_service():
    hour = 3600
    blocks = {
        "X": {"start": 6 * hour, "end": 10 * hour},
        "Y": {"start": 7 * hour, "end": 9 * hour},
        "Z": {"start": 9 * hour, "end": 12 * hour},  # starts exactly as Y ends
    }
    # 07:00-09:00 X and Y run; 09:00-10:00 X and Z run. Y and Z only touch: peak 2, not 3.
    assert peak_blocks_in_service(blocks) == 2


def test_fleet_size_everything_fits(summary):
    # A and B never overlap, so one bus does the day today; both fit in 180 km.
    result = fleet_size(summary, "winter", **SETTINGS)
    assert result["buses_needed_today"] == 1
    assert result["blocks_over_range"] == 0
    assert result["electric_buses_needed"] == 1
    assert result["replacement_ratio"] == 1.0
    assert result["benchmark_ratio"] == 1.2


def test_fleet_size_with_a_block_over_range(summary):
    # B is over the 25 km range, so it needs one extra bus: 1 + 1 = 2, a ratio of 2.0.
    result = fleet_size(summary, "winter", **TINY_BATTERY)
    assert result["blocks_over_range"] == 1
    assert result["electric_buses_needed"] == 2
    assert result["replacement_ratio"] == 2.0


def test_charging_needs(summary):
    # (25 + 30) km x 2.0 kWh/km = 110 kWh overnight; spread over 6 h = 18.3 kW at the depot.
    result = charging_needs(summary, "winter", **SETTINGS)
    assert result["daily_km"] == 55.0
    assert result["overnight_energy_kwh"] == 110.0
    assert result["peak_depot_power_kw"] == pytest.approx(18.3, abs=0.05)


def test_cost_and_co2(summary):
    result = cost_and_co2(summary, "winter", **SETTINGS)
    # Every electric bus needed is priced: 1 bus and 1 charger = 1,200,000 + 150,000 = 1,350,000.
    assert (result["electric_buses_priced"], result["of_which_extra_buses"]) == (1, 0)
    assert (result["chargers"], result["capital_cost"]) == (1, 1_350_000)
    # 55 km a day x 300 days = 16,500 km a year.
    assert result["annual_km"] == 16_500
    # Electric: 16,500 km x 2.0 kWh/km x 0.15 = 4,950. Diesel: 16,500 x 0.55 L x 1.70 = 15,427.50.
    assert result["annual_electricity_cost"] == 4_950
    assert result["annual_diesel_cost"] == round(15_427.5)
    # CO2: 16,500 km x 0.55 L/km x 2.68 kg/L = 24,321 kg = 24.3 tonnes.
    assert result["annual_co2_saved_tonnes"] == 24.3


def test_capital_cost_with_a_block_over_range(summary):
    # 2 electric buses (1 replacement + 1 extra) and 2 chargers:
    # 2 x 1,200,000 + 2 x 150,000 = 2,700,000.
    result = cost_and_co2(summary, "winter", **TINY_BATTERY)
    assert (result["electric_buses_priced"], result["of_which_extra_buses"]) == (2, 1)
    assert (result["chargers"], result["capital_cost"]) == (2, 2_700_000)


def test_all_in_price_with_charger_included(summary):
    # Halifax-style all-in price per bus with its charger, so the charger price is 0:
    # 1 electric bus x 1,578,998 + 1 charger x 0 = 1,578,998.
    settings = {**SETTINGS, "electric_bus_price": 94_739_857 / 60, "charger_price": 0}
    result = cost_and_co2(summary, "winter", **settings)
    assert result["capital_cost"] == 1_578_998
    assert result["assumptions"]["electric_bus_price"] == 1_578_998


def test_every_assumption_is_reported_with_a_source(summary):
    for tool in (fleet_size, charging_needs, cost_and_co2):
        assumptions = tool(summary, "winter")["assumptions"]
        sources = assumptions["sources"]
        for name in assumptions:
            if name in ("usable_kwh", "notes", "sources"):
                continue  # derived values and notes, not assumptions
            assert name in sources, f"{tool.__name__}: no source for {name}"
            assert sources[name]["status"] in ("SOURCED", "PLACEHOLDER", "CHOICE")


def test_winter_energy_cites_both_sources(summary):
    sources = fleet_size(summary, "winter")["assumptions"]["sources"]
    winter = sources["kwh_per_km"]
    assert winter["status"] == "SOURCED" and winter["pages"] == "1"
    assert "1.22" in winter["note"] and "1.425" in winter["note"]  # TTC summer x Finnish uplift
    assert sources["replacement_ratio_benchmark"]["status"] == "PLACEHOLDER"
    summer = fleet_size(summary, "summer")["assumptions"]["sources"]["kwh_per_km"]
    assert summer["pages"] == "55"
    assert summer["url"].startswith("https://www.ttc.ca/")


def test_shares_over_range_are_returned(summary):
    # Tiny battery: B (30 km) is over the 25 km range, A (25 km) fits: 1 of 2 = 50% over.
    assert fleet_size(summary, "winter", **TINY_BATTERY)["pct_over_range"] == 50.0


def test_costs_are_reported_in_the_agencys_currency(mini_feed):
    # The same mini feed and CAD prices, built as Dublin (EUR), London (GBP) and an agency with
    # no currency set (CAD): money is divided by the rate, everything else is unchanged.
    rates = {"CAD": 1.0, "EUR": 1.5, "GBP": 2.0}
    cad = cost_and_co2(build_summary(mini_feed, "mini"), "winter", **SETTINGS, cad_per_currency_unit=rates)
    eur = cost_and_co2(build_summary(mini_feed, "dublin"), "winter", **SETTINGS, cad_per_currency_unit=rates)
    gbp = cost_and_co2(build_summary(mini_feed, "london"), "winter", **SETTINGS, cad_per_currency_unit=rates)
    assert (cad["currency"], eur["currency"], gbp["currency"]) == ("CAD", "EUR", "GBP")
    assert "converted_from" not in cad
    assert eur["converted_from"] == "CAD prices at 1 EUR = 1.5 CAD"
    assert eur["capital_cost"] == round(cad["capital_cost"] / 1.5)
    assert abs(gbp["annual_energy_saving"] - cad["annual_energy_saving"] / 2.0) <= 1  # rounding
    assert gbp["annual_co2_saved_tonnes"] == cad["annual_co2_saved_tonnes"]
    assert gbp["assumptions"]["electric_bus_price"] == SETTINGS["electric_bus_price"]  # prices stay CAD
    # ...and are also given converted, so an answer never has to relabel a CAD price as pounds.
    assert gbp["prices_in_GBP"] == {"electric_bus_price": 600_000, "charger_price": 75_000,
                                    "electricity_price_per_kwh": 0.075, "diesel_price_per_litre": 0.85}
    assert "prices_in_CAD" not in cad
