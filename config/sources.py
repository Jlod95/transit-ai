"""Public documents the agent can cite, and how each one may be used.

Licensing, kept deliberately safe: only documents with an explicit open licence are indexed as
full text (copied passages). For every other document the index holds FACT CARDS instead:
short statements of individual figures, written in our own words, with the page and link.
Figures (facts) aren't protected by copyright; the documents' own wording is, so it isn't copied.

Every fact card was checked against the page it cites. The PDFs live in data/raw/sources/
(not committed); scripts/build_source_index.py reads them and writes data/index/sources.json.
"""

DOCUMENTS = [
    {
        "id": "vtt_winter_2022",
        "title": "Setting Up and Operating Electric City Buses in Harsh Winter Conditions",
        "publisher": "Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI)",
        "date": "2022-03",
        "url": "https://www.mdpi.com/2076-3417/12/6/2762",
        "file": "applsci-12-02762-v2.pdf",
        "licence": "CC BY 4.0 (stated on page 1)",
        "use": "full_text",
    },
    {
        "id": "halifax_beb_contract_2022",
        "title": "Award - RFP 21-021: Supply and Deliver up to Sixty 40 Foot Battery Electric "
                 "Transit Buses and Chargers",
        "publisher": "Halifax Regional Council report",
        "date": "2022-05-17",
        "url": "https://www.halifax.ca/media/77822",
        "file": "halifax_beb_contract_2022.pdf",
        "licence": "Public record, no open licence: fact cards only",
        "use": "facts_only",
    },
    {
        "id": "ttc_ebus_evaluation_2022",
        "title": "TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation",
        "publisher": "Toronto Transit Commission board report",
        "date": "2022-04-14",
        "url": "https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14",
        "file": "ttc_ebus_evaluation_2022.pdf",
        "licence": "Public record, no open licence: fact cards only",
        "use": "facts_only",
    },
    {
        "id": "nrel_beb_financial_2020",
        "title": "Financial Analysis of Battery Electric Transit Buses",
        "publisher": "National Renewable Energy Laboratory (US Department of Energy)",
        "date": "2020-06",
        "url": "https://afdc.energy.gov/files/u/publication/financial_analysis_be_transit_buses.pdf",
        "file": "nrel_beb_financial_analysis_2020.pdf",
        "licence": "Publicly released government lab report: fact cards only",
        "use": "facts_only",
    },
    {
        "id": "tfl_bus_action_plan_2022",
        "title": "Bus action plan",
        "publisher": "Transport for London",
        "date": "2022-03",
        "url": "https://content.tfl.gov.uk/bus-action-plan.pdf",
        "file": "tfl_bus_action_plan_2022.pdf",
        "licence": "Public document, no open licence stated: fact cards only",
        "use": "facts_only",
    },
    {
        "id": "nrcan_fuel_co2_factsheet",
        "title": "Learn the facts: Fuel consumption and CO2 (AutoSmart factsheet 6)",
        "publisher": "Natural Resources Canada",
        "date": "2014",
        "url": "https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/"
               "fuel-efficient-technologies/autosmart_factsheet_6_e.pdf",
        "file": "nrcan_fuel_co2_factsheet.pdf",
        "licence": "Government of Canada publication: fact cards only",
        "use": "facts_only",
    },
    {
        "id": "ie_bus_trials_2019",
        "title": "Report on Diesel and Alternative-Fuel Bus Trials",
        "publisher": "Department of Transport, Tourism and Sport (Ireland)",
        "date": "2019-12",
        "url": "https://www.gov.ie/en/publication/7251e2-low-emission-bus-trials-report/",
        "file": "report-on-diesel-and-alternative-fuel-bus-trials.pdf",
        "licence": "No licence stated in the document: fact cards only",
        "use": "facts_only",
    },
]

# Our own short statements of individual figures. Each cites one page.
FACT_CARDS = [
    ("halifax_beb_contract_2022", 2,
     ("Halifax Regional Council (May 2022) awarded Nova Bus Ltd. a contract for up to 60 forty-foot "
     "battery-electric buses with chargers, 30 in 2022/23 and 30 in 2023/24, for a total purchase "
     "price of $94,739,857 (Canadian dollars, net HST included).")),
    ("halifax_beb_contract_2022", 2,
     ("Halifax's 60 battery-electric buses replace 60 diesel buses at the end of their useful life; "
     "the wider project also expands the Ragged Lake Transit Centre to accommodate battery-electric "
     "buses.")),
    ("ttc_ebus_evaluation_2022", 55,
     ("Toronto (TTC) in-service range estimates, 2021: BYD (360 kWh battery, 291 kWh usable) used "
     "1.06 kWh/km in summer and 1.47 kWh/km in winter, ranges about 274 km and 198 km; New Flyer "
     "(400 kWh, 285 usable) 1.22 and 1.40 kWh/km, 234 and 203 km; Proterra (440 kWh, 271 usable) "
     "1.28 and 1.68 kWh/km, 212 and 161 km.")),
    ("ttc_ebus_evaluation_2022", 55,
     ("Toronto (TTC) in-service range estimates, 2020: BYD 1.18 kWh/km summer and 1.37 kWh/km "
     "winter (about 246 km and 212 km); New Flyer 1.30 and 1.39 kWh/km (219 and 205 km); Proterra "
     "1.27 and 1.76 kWh/km (213 and 153 km).")),
    ("ttc_ebus_evaluation_2022", 68,
     ("Toronto (TTC) 2021 engineering tests on routes: BYD averaged 1.14 kWh/km in summer and "
     "1.66 kWh/km in winter; New Flyer 1.21 and 1.32 kWh/km; Proterra 1.27 and 1.56 kWh/km.")),
    ("ttc_ebus_evaluation_2022", 44,
     "In Toronto's eBus trial, monthly energy use per km was highest in the colder months."),
    ("ttc_ebus_evaluation_2022", 24,
     ("Toronto's large eBus tender (April 2022) required two rear charging ports accepting at least "
     "150 kW.")),
    ("ttc_ebus_evaluation_2022", 6,
     ("Toronto (TTC) plans to buy only zero-emission buses from 2024 and to have a fully "
     "zero-emission fleet by 2040.")),
    ("ttc_ebus_evaluation_2022", 3,
     ("The TTC estimates its zero-emission bus programme will cut greenhouse gas emissions by about "
     "250,000 tonnes of CO2 a year.")),
    ("nrel_beb_financial_2020", 15,
     ("NREL baseline (2020, US dollars): a 40-foot battery-electric bus costs $887,308; its energy "
     "use is 1.82 kWh per mile (from Altoona tests of Proterra, BYD and Nova buses).")),
    ("nrel_beb_financial_2020", 14,
     "NREL baseline (2020, US dollars): a new 40-foot diesel bus costs $480,000."),
    ("nrel_beb_financial_2020", 15,
     ("NREL baseline (2020, US dollars): a depot charger costs $50,000 plus $17,050 installation, "
     "with one depot charger per bus; an on-route fast charger costs $495,636 plus $202,811 "
     "installation and can serve up to eight buses.")),
    ("nrel_beb_financial_2020", 21,
     ("In NREL's example US bus depot, the average daily peak electricity demand was about 800 kW "
     "and the monthly peak up to about 1,100 kW, before adding battery-electric buses.")),
    ("tfl_bus_action_plan_2022", 73,
     ("TfL brought forward its target for a fully zero-emission London bus fleet from 2037 to 2034, "
     "saving 600,000 tonnes of carbon; the Mayor's ambition is 2030, and every bus garage would "
     "need converting to electric charging or hydrogen fuelling.")),
    ("tfl_bus_action_plan_2022", 8,
     ("TfL says delivering a zero-emission bus fleet by 2030 would remove 500,000 tonnes of carbon "
     "emissions a year from London's transport system.")),
    ("tfl_bus_action_plan_2022", 72,
     ("In March 2022 London had more than 700 zero-emission buses, and TfL aimed for 10% of the bus "
     "fleet to be zero-emission by the end of 2022.")),
    ("nrcan_fuel_co2_factsheet", 2,
     ("Natural Resources Canada: burning a litre of diesel releases 2.66 kg of CO2 at the tailpipe "
     "(B5 biodiesel blend 2.65 kg, B20 2.62 kg, gasoline 2.29 kg).")),
    ("ie_bus_trials_2019", 37,
     ("Irish bus trials (Dublin and Cork): electric buses averaged 7.5 MJ/km, including diesel used "
     "by one bus's heater, or 6.8 MJ/km without that bus; the most efficient averaged 5.6 MJ/km. "
     "The report defines 1 kWh as 3.6 MJ.")),
    ("ie_bus_trials_2019", 37,
     ("Irish bus trials: colder temperatures went with higher electric bus energy use, and one "
     "electric bus was about 35-40% less efficient in Dublin than in Cork; on average the buses "
     "used 7.8 MJ/km in Dublin and 7.3 MJ/km in Cork.")),
    ("ie_bus_trials_2019", 24,
     ("Ireland's urban public bus fleet used 16.6 MJ per km in 2018 (about 46 litres of diesel per "
     "100 km); across urban, regional and intercity services it was 14.7 MJ/km (41 l/100 km).")),
]
