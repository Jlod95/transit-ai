"""Assumptions for the electric bus feasibility check.

All values are rough placeholders so the pipeline works end to end. Replace them with
sourced figures (manufacturer specs, agency or published operating data) before relying on results.
"""

# Battery size on the spec sheet, in kWh.
nominal_battery_kwh = 450  # PLACEHOLDER - to be sourced in M4

# Share of the nominal battery used in daily service. Industry practice; routinely
# discharging below 20% accelerates long-term battery degradation and removes the reserve
# for delays and cold.
usable_fraction = 0.8

# Energy used per km driven, by season. Winter is higher mainly because of cabin heating.
kwh_per_km = {"summer": 1.3, "winter": 2.0}  # PLACEHOLDER - to be sourced in M4

# --- Fleet, charging, cost and CO2 (used by src/fleet.py) ---

# Electric buses needed per diesel bus replaced, as commonly quoted for early battery-electric
# fleets; shown only as a benchmark next to the computed ratio.
replacement_ratio_benchmark = 1.2  # PLACEHOLDER - to be sourced in M4

# Hours overnight in which every bus must finish charging at the depot.
charging_window_hours = 6  # PLACEHOLDER - to be sourced in M4

# Depot chargers: how many buses share one charger overnight.
buses_per_charger = 1  # PLACEHOLDER - to be sourced in M4

# Prices, in one currency for every agency (crude: no exchange rates or local prices).
currency = "CAD"  # PLACEHOLDER - to be sourced in M4
electric_bus_price = 1_200_000  # per bus. PLACEHOLDER - to be sourced in M4
charger_price = 150_000  # per depot charger, installed. PLACEHOLDER - to be sourced in M4
electricity_price_per_kwh = 0.15  # PLACEHOLDER - to be sourced in M4
diesel_price_per_litre = 1.70  # PLACEHOLDER - to be sourced in M4

# Diesel bus fuel use and the CO2 released by burning a litre of diesel.
diesel_litres_per_km = 0.55  # PLACEHOLDER - to be sourced in M4
kg_co2_per_litre_diesel = 2.68  # PLACEHOLDER - to be sourced in M4

# Annual km = design-day km x this many days. The design day is the busiest pattern, so this
# is fewer than 365 to allow for lighter weekends and holidays.
annual_service_days = 300  # PLACEHOLDER - to be sourced in M4
