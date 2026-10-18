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
