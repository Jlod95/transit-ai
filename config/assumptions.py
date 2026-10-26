"""Assumptions for the electric bus feasibility check, each with its source.

Values marked SOURCED come from documents in the public-sources index (config/sources.py);
ASSUMPTION_SOURCES below gives the title, page, URL and any conversion for each. Values marked
PLACEHOLDER have no published figure in the index yet and are rough guesses. The tools report
every value next to its source or placeholder label.
"""

# --- Battery and energy (SOURCED) ---

# Battery size on the spec sheet: New Flyer 40-ft bus in Toronto's trial.
nominal_battery_kwh = 400  # SOURCED: TTC eBus evaluation, p. 55

# Share of the nominal battery usable in service: 285 of 400 kWh for the same bus.
usable_fraction = 285 / 400  # SOURCED: TTC eBus evaluation, p. 55 (= 0.7125)

# Energy used per km. Summer: the same New Flyer bus in Toronto. Winter: summer x the Finnish
# finding that winter use was 40-45% higher (midpoint 42.5%), because Toronto's winter figure
# excludes the diesel its buses burned for heating.
_TTC_SUMMER_KWH_PER_KM = 1.22  # SOURCED: TTC eBus evaluation, p. 55
_FINNISH_WINTER_UPLIFT = 1.425  # SOURCED: Vehviläinen et al. 2022, p. 1 (40-45% higher)
kwh_per_km = {
    "summer": _TTC_SUMMER_KWH_PER_KM,
    "winter": _TTC_SUMMER_KWH_PER_KM * _FINNISH_WINTER_UPLIFT,  # = 1.7385
}

# --- Fleet, charging, cost and CO2 (used by src/fleet.py) ---

# Electric buses needed per diesel bus replaced, as commonly quoted for early battery-electric
# fleets; shown only as a benchmark next to the computed ratio.
replacement_ratio_benchmark = 1.2  # PLACEHOLDER - no published figure in the index

# Hours overnight in which every bus must finish charging at the depot.
charging_window_hours = 6  # PLACEHOLDER - no published figure in the index

# Depot chargers: one per bus.
buses_per_charger = 1  # SOURCED: NREL financial analysis, p. 15

# Prices, all in one currency (crude: Halifax-based prices, no local Irish or UK prices).
currency = "CAD"  # Halifax's contract is in Canadian dollars
# Canadian dollars per unit of each currency costs are reported in: Dublin answers in euros and
# London answers in pounds are these CAD prices converted, not local prices.
cad_per_currency_unit = {"CAD": 1.0, "EUR": 1.5782, "GBP": 1.8420}  # SOURCED: Bank of Canada, 2025 annual averages
# All-in price of one electric bus with its charger: Halifax's contract total / 60 buses.
electric_bus_price = 94_739_857 / 60  # SOURCED: Halifax council report, p. 2 (= 1,578,998)
charger_price = 0  # SOURCED: included in electric_bus_price above
electricity_price_per_kwh = 0.15  # PLACEHOLDER - no published figure in the index
diesel_price_per_litre = 1.70  # PLACEHOLDER - no published figure in the index

# Diesel bus fuel use and the CO2 released by burning a litre of diesel.
diesel_litres_per_km = 46 / 100  # SOURCED: Irish bus trials report, p. 24 (46 L/100 km)
kg_co2_per_litre_diesel = 2.66  # SOURCED: Natural Resources Canada factsheet, p. 2

# Annual km = design-day km x this many days. The design day is the busiest pattern, so this
# is fewer than 365 to allow for lighter weekends and holidays.
annual_service_days = 300  # PLACEHOLDER - no published figure in the index


_TTC = {
    "title": "TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation",
    "publisher": "Toronto Transit Commission",
    "url": "https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14",
}
_FINNISH = {
    "title": "Setting Up and Operating Electric City Buses in Harsh Winter Conditions",
    "publisher": "Vehviläinen et al., Applied Sciences 12(6) 2762, 2022 (CC BY 4.0)",
    "url": "https://www.mdpi.com/2076-3417/12/6/2762",
}
_NREL = {
    "title": "Financial Analysis of Battery Electric Transit Buses",
    "publisher": "National Renewable Energy Laboratory, 2020",
    "url": "https://afdc.energy.gov/files/u/publication/financial_analysis_be_transit_buses.pdf",
}
_HALIFAX = {
    "title": "Award - RFP 21-021: Supply and Deliver up to Sixty 40 Foot Battery Electric Transit "
             "Buses and Chargers",
    "publisher": "Halifax Regional Council report, 17 May 2022",
    "url": "https://www.halifax.ca/media/77822",
}
_BANK_OF_CANADA = {
    "title": "Annual exchange rates",
    "publisher": "Bank of Canada",
    "url": "https://www.bankofcanada.ca/rates/exchange/annual-average-exchange-rates/",
}
_IRISH = {
    "title": "Report on Diesel and Alternative-Fuel Bus Trials",
    "publisher": "Department of Transport, Tourism and Sport (Ireland), December 2019",
    "url": "https://www.gov.ie/en/publication/7251e2-low-emission-bus-trials-report/",
}
_NRCAN = {
    "title": "Learn the facts: Fuel consumption and CO2 (AutoSmart factsheet 6)",
    "publisher": "Natural Resources Canada",
    "url": "https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/"
           "fuel-efficient-technologies/autosmart_factsheet_6_e.pdf",
}


def _placeholder(note):
    return {"status": "PLACEHOLDER", "note": note}


# Where each value comes from. Tools copy these next to the values they use.
ASSUMPTION_SOURCES = {
    "nominal_battery_kwh": {**_TTC, "status": "SOURCED", "pages": "55",
                            "note": "New Flyer 40-ft bus battery, 400 kWh"},
    "usable_fraction": {**_TTC, "status": "SOURCED", "pages": "55",
                        "note": "285 usable / 400 kWh = 0.7125, measured in service"},
    "kwh_per_km": {
        "status": "SOURCED",
        "summer": {**_TTC, "pages": "55", "note": "New Flyer, 2021 in-service average: 1.22 kWh/km"},
        "winter": {**_FINNISH, "pages": "1",
                   "note": "1.22 (TTC summer) x 1.425, the midpoint of the Finnish finding that "
                           "winter use is 40-45% higher than summer = 1.7385 kWh/km. TTC's own "
                           "winter figure (1.40, p. 55) is not used because its New Flyer buses "
                           "also burned diesel for heating (pp. 47, 61)"},
    },
    "replacement_ratio_benchmark": _placeholder("commonly quoted planning figure; not in the index"),
    "charging_window_hours": _placeholder("assumed overnight window; not in the index"),
    "buses_per_charger": {**_NREL, "status": "SOURCED", "pages": "15",
                          "note": "one depot charger per bus"},
    "currency": {"status": "CHOICE", "note": "Canadian dollars, the currency of the Halifax price; "
                                            "every price above is in CAD"},
    "cad_per_currency_unit": {**_BANK_OF_CANADA, "status": "SOURCED", "pages": "2025",
                              "note": "2025 annual average: 1 EUR = 1.5782 CAD, 1 GBP = 1.8420 CAD; "
                                      "used to report Halifax-based CAD costs in euros (Dublin) "
                                      "and pounds (London)"},
    "electric_bus_price": {**_HALIFAX, "status": "SOURCED", "pages": "2",
                           "note": "all-in price per bus including its charger: "
                                   "$94,739,857 / 60 buses = $1,578,998 (CAD, net HST)"},
    "charger_price": {**_HALIFAX, "status": "SOURCED", "pages": "2",
                      "note": "0: chargers are included in the all-in bus price"},
    "electricity_price_per_kwh": _placeholder("no published price in the index"),
    "diesel_price_per_litre": _placeholder("no published price in the index"),
    "diesel_litres_per_km": {**_IRISH, "status": "SOURCED", "pages": "24",
                             "note": "Irish urban bus fleet 2018: 46 L/100 km = 0.46 L/km"},
    "kg_co2_per_litre_diesel": {**_NRCAN, "status": "SOURCED", "pages": "2",
                                "note": "tailpipe CO2 from diesel: 2.66 kg per litre"},
    "annual_service_days": _placeholder("assumed weekday-equivalent days per year; not in the index"),
}


def sources_for(*names):
    """{name: source} for the named assumptions, to report next to their values."""
    return {name: ASSUMPTION_SOURCES[name] for name in names}
