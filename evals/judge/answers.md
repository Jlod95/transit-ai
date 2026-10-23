# Answers to label

Twenty agent answers, numbered 1-20. For each, fill in a row of `my_labels.csv` with Y or N per criterion (and a note if useful). The criteria:

- **conclusion**: The conclusion is consistent with the tool numbers (no wrong inference, swapped roles or wrong comparison drawn from correct numbers).
- **answers_question**: It answers the question that was asked (the right agency, block, date and quantity), not a different one.
- **caveats**: The caveats the tool output calls for are present, judged by meaning, not keywords: estimated distances or inferred blocks, placeholder assumptions, data limits (e.g. deadhead excluded, dates outside the timetable). N if one is missing.
- **no_misleading**: No misleading or unsupported claims: every figure and statement is backed by the tool output or plainly marked as general knowledge, with no invented numbers.
- **clear**: Clear enough for a transit planner to forward as it is, without rewriting.

---

## 1

**Agency:** halifax

**Question:** Which day should Halifax Transit plan its electric fleet around in winter, and how many blocks would be too long for one charge that day?

**Key tool numbers:**

- `get_design_day({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, same_pattern_dates: 10, rule: most blocks over range, then most blocks in service, then earliest date, blocks_over_range: 130, season: winter, range_km: 163.9, total_blocks: 461, within_range: 331, exceeding_range: 130, pct_within_range: 71.8, pct_exceeding_range: 28.2

**Answer:**

**Design day (winter): Monday 24 August 2026.** Ten dates in the timetable share this pattern: 24–28 Aug, 31 Aug, 1–2 Sep, 25 Sep and 23 Oct 2026. The tool picks the day with the most blocks over range, then the most blocks in service, then the earliest date.

**Blocks too long for one charge that day: 130 of 461.**
- 331 blocks (71.8%) fit within one charge.
- 130 blocks (28.2%) exceed it.
- The range used is 163.9 km.
- The five longest blocks are 722134 (457.5 km), 722151 (364.8 km), 722165 (363.5 km), 722252 (363.2 km) and 712134 (363.0 km).

**Assumptions**
- Battery: 400 kWh nominal, with 71.25% usable (285 kWh). Both come from the TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation, p. 55 (https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14).
- Winter energy use: 1.7385 kWh/km. This is the TTC summer figure of 1.22 multiplied by 1.425, which is the midpoint of the Finnish finding that winter use is 40–45% higher. Source: Vehviläinen et al., Applied Sciences 12(6) 2762, 2022, p. 1 (https://www.mdpi.com/2076-3417/12/6/2762). The tool did not use the TTC's own winter figure because those buses also burned diesel for heating.
- The model assumes one overnight charge and no daytime charging. It uses revenue km only, with no deadhead, so it is optimistic. The real number of blocks over range could be higher.

**Data:** Halifax feed version 2026_08_August_20260806. Distances are exact, taken from shape_dist_traveled, and the block IDs are the ones published in the feed. The timetable covers 24 Aug to 29 Nov 2026.

---

## 2

**Agency:** halifax

**Question:** How many Halifax Transit blocks could run on one overnight charge in winter on 18 November 2026?

**Key tool numbers:**

- `get_fleet_feasibility({"agency": "halifax", "date": "2026-11-18", "season": "winter"})`: service_date: 2026-11-18, season: winter, range_km: 163.9, total_blocks: 461, within_range: 331, exceeding_range: 130, pct_within_range: 71.8, pct_exceeding_range: 28.2

**Answer:**

On 18 November 2026, **331 of 461 Halifax Transit blocks (71.8%)** could run on one overnight winter charge. The other **130 blocks (28.2%)** exceed the range.

- **Range:** 163.9 km per charge in winter.
- **Longest blocks:** 722134 (457.5 km), 722151 (364.8 km), 722165 (363.5 km), 722252 (363.2 km), and 712134 (363.0 km).
- **Method:** The battery is 400 kWh nominal with 71.25% usable (285 kWh). Winter energy use is 1.7385 kWh/km. Distances are exact, taken from the feed's shape distances. Blocks are the feed's published block IDs, not inferred. Revenue km only, so empty garage trips are excluded, which makes this optimistic. There is no daytime charging.
- **Data:** Halifax feed version 2026_08_August_20260806, covering the timetable from 2026-08-24 to 2026-11-29.

**Sources:**
- **Battery size (400 kWh) and usable fraction (71.25%, 285 kWh):** *TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, Toronto Transit Commission, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14. These are sourced values.
- **Winter energy use (1.7385 kWh/km):** *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, Vehviläinen et al., Applied Sciences 12(6), 2762 (2022), p. 1, https://www.mdpi.com/2076-3417/12/6/2762. The tool derived this by multiplying the TTC summer figure of 1.22 kWh/km by 1.425, the midpoint of the Finnish finding that winter use is 40–45% higher than summer. It is a derived value from sourced inputs, not a directly measured winter figure. The tool did not use TTC's own winter figure of 1.40 kWh/km (p. 55), because those buses also burned diesel for heating.

---

## 3

**Agency:** halifax

**Question:** Roughly what would electrifying Halifax Transit's buses cost, and how much CO2 would it save each year? Assume winter energy use.

**Key tool numbers:**

- `get_cost_and_co2({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, season: winter, currency: CAD, electric_buses_priced: 414, of_which_extra_buses: 130, chargers: 414, capital_cost: 653705013, annual_km: 15894900, annual_electricity_cost: 4144993, annual_diesel_cost: 12429812, annual_energy_saving: 8284819, annual_co2_saved_tonnes: 19449.0

**Answer:**

**Short answer:** Replacing Halifax Transit's design-day fleet with electric buses would cost about **CAD 654 million** in capital, and would save about **19,449 tonnes of CO2 a year** from avoided diesel. Both figures are crude and rest on placeholder inputs, as explained below.

**Capital cost (CAD 653,705,013)**
- The fleet needs 414 electric buses: 284 replacements for today's buses plus 130 extra buses to cover blocks that exceed one charge's range in winter.
- Each bus is priced at CAD 1,578,998 with its charger included.
- Spare buses and grid upgrades are not included.
- Bus price source: Halifax Regional Council, "Award - RFP 21-021" (17 May 2022), p. 2, https://www.halifax.ca/media/77822

**Annual CO2 saved (19,449 tonnes)**
- Calculated from avoided diesel use over 15,894,900 annual km.
- Electricity generation emissions are not subtracted, so this is a tailpipe-based figure.
- Diesel use of 0.46 L/km is from the Irish Department of Transport, Tourism and Sport, "Report on Diesel and Alternative-Fuel Bus Trials" (Dec 2019), p. 24, https://www.gov.ie/en/publication/7251e2-low-emission-bus-trials-report/
- The 2.66 kg CO2 per litre of diesel is from Natural Resources Canada, "Learn the facts: Fuel consumption and CO2" (AutoSmart factsheet 6), p. 2, https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/fuel-efficient-technologies/autosmart_factsheet_6_e.pdf

**Winter energy assumption**
- Winter energy use is 1.7385 kWh/km. This is the TTC summer figure of 1.22 kWh/km multiplied by 1.425, the midpoint of the 40–45% winter uplift in Vehviläinen et al., Applied Sciences 12(6) 2762 (2022), p. 1, https://www.mdpi.com/2076-3417/12/6/2762
- Battery size (400 kWh nominal, 71.25% usable) is from TTC, "Final Results of TTC's Head-to-Head eBus Evaluation" (2022), p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14

**Running costs (placeholders, not sourced)**
- Annual electricity cost: CAD 4,144,993. Annual diesel cost: CAD 12,429,812. Annual saving: CAD 8,284,819.
- These use placeholder prices of CAD 0.15/kWh for electricity and CAD 1.70/L for diesel, and 300 service days a year. No published source in the index covers these, so treat them as illustrative only.

**Other caveats**
- The tool's design day is 2026-08-24, a late-summer date, because it selects the hardest day in the timetable for the season. The winter energy figure is applied to that day's blocks.
- The timetable feed is halifax.zip, version 2026_08_August_20260806, covering 2026-08-24 to 2026-11-29. Distances come from the feed's shape distances, and blocks use the published block IDs.
- The results are revenue km only, so they are optimistic.

---

## 4

**Agency:** dublin

**Question:** How many electric buses would Dublin (Dublin Bus and Go-Ahead Ireland) need in summer, compared with today, and what is the replacement ratio?

**Key tool numbers:**

- `get_fleet_size({"agency": "dublin", "season": "summer"})`: design_day: 2026-10-24, season: summer, range_km: 233.6, blocks_in_service: 1172, buses_needed_today: 799, blocks_over_range: 187, pct_over_range: 16.0, electric_buses_needed: 986, replacement_ratio: 1.234, benchmark_ratio: 1.2

**Answer:**

**Summer result for Dublin (Dublin Bus and Go-Ahead Ireland):**

- **Buses today:** 799
- **Electric buses needed:** 986
- **Replacement ratio:** 1.234 (electric buses ÷ buses today)

**How the figure is built:** The design day is 2026-10-24, the day with the most blocks in service at the same moment, which gives 1,172 blocks. Of these, 187 blocks (16.0%) are over the summer range of 233.6 km. Each of those blocks needs one extra bus, which takes the count from 799 to 986. This assumes a fresh bus swaps in mid-day. The count excludes spare buses.

**Range assumptions:**
- Battery: 400 kWh nominal, with 71.25% usable (285 kWh). Source: TTC, *Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14. The 400 kWh figure is for a New Flyer 40-ft bus, and the 71.25% usable fraction was measured in service.
- Energy use: 1.22 kWh/km, the New Flyer 2021 in-service average. Source: same TTC document, p. 55.
- One overnight charge, no daytime charging, revenue km only (no empty running to and from the garage). Because deadhead distance is excluded, the range need is probably understated, so treat the result as optimistic.

**Benchmark:** The tool compares the 1.234 ratio with a 1:1.2 planning benchmark. That benchmark is a **placeholder** (a commonly quoted figure, not from the source index), so I cannot cite it. The result is about 0.03 above it.

**Data quality:** Block distances are exact, taken from the trip shapes in the feed, and blocks use the feed's published block IDs. Neither is estimated or inferred. The figures come from feed version 7F45B939-88CD-4972-AC8A-1992A136F855 (dublin_bus.zip and dublin_goahead.zip), covering the timetable from 2026-10-18 to 2027-01-30.

---

## 5

**Agency:** halifax

**Question:** How far does block 711399 drive on 6 February 2027?

**Key tool numbers:**

- `get_block_distance({"agency": "halifax", "block_id": "711399", "date": "2027-02-06"})`: 2027-02-06 is outside the dates available for Halifax Transit: 2026-08-24 to 2026-11-29 (whole timetable).

**Answer:**

I can't give a distance for block 711399 on 6 February 2027. That date isn't in Halifax Transit's current timetable, which only runs from **24 August 2026 to 29 November 2026**. There's no schedule data for February 2027 yet, so I can't tell you how far the block will drive that day.

Here are some options:
- **Check a date within that range.** For example, if you want a Saturday like 6 February 2027, I could look up a Saturday such as 28 November 2026. Block numbers and schedules can change when a new timetable comes in, though, so that would only be a rough guide for February.
- **Look at winter conditions instead.** If you're asking because of battery range in winter, I can check this block against winter energy use on a date in the current timetable.

Do you want me to look up block 711399 on one of those dates?

---

## 6

**Agency:** halifax

**Question:** What is the average number of passengers on a Halifax Transit bus at rush hour?

**Key tool numbers:**

- `search_sources({"query": "Halifax Transit average passengers per bus at rush hour ridership", "k": 5})`: Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 14); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 13); Award - RFP 21-021: Supply and Deliver up to Sixty 40 Foot Battery Electric Transit Buses and Chargers (Halifax Regional Council report, 2); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 14-15); TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation (Toronto Transit Commission board report, 55)

**Answer:**

I can't give you the average rush-hour passenger count for Halifax Transit. None of the sources I can search contain Halifax ridership or load data, and the tools I have cover block distances, service times, fleet, charging and cost, not passenger numbers.

The only related figure I found is from a Tampere, Finland study, and it doesn't apply to Halifax. Vehviläinen et al., "Setting Up and Operating Electric City Buses in Harsh Winter Conditions," *Applied Sciences* 12(6), 2762 (MDPI, 2022), pages 13–14, https://www.mdpi.com/2076-3417/12/6/2762, estimates that the passenger number on one bus "simultaneously during peak hours is ~50." The same passage notes that exact passenger counts were not available, because only boarding passengers were recorded.

For Halifax figures, you would need ridership or automatic passenger counter data from Halifax Transit itself. Its published ridership reports or a data request to the agency would be the place to look.

---

## 7

**Agency:** london

**Question:** Roughly what would electrifying London (TfL buses)'s buses cost, and how much CO2 would it save each year? Assume winter energy use.

**Key tool numbers:**

- `get_cost_and_co2({"agency": "london", "season": "winter"})`: design_day: 2026-10-22, season: winter, currency: CAD, electric_buses_priced: 13603, of_which_extra_buses: 5559, chargers: 13603, capital_cost: 21479104580, annual_km: 457554120, annual_electricity_cost: 119318676, annual_diesel_cost: 357807322, annual_energy_saving: 238488646, annual_co2_saved_tonnes: 559863.2

**Answer:**

Electrifying London's buses would cost roughly **CAD 21.5 billion** up front and save roughly **560,000 tonnes of CO₂ a year**, based on winter energy use. Treat both figures as order-of-magnitude estimates.

**The data behind this**
- The figures come from the London (TfL) timetable feed version `20261020_032409`. The hardest day in that timetable for electric buses is 22 Oct 2026.
- **Bus schedules are guessed.** London's timetable doesn't say which trips one bus runs in a day, so they were worked out route by route. Buses aren't assumed to switch routes during the day, and operators are approximated.
- **Distances are estimated.** They are straight lines between stops, stretched by a road factor of 1.1183. That factor was checked against exact Dublin route distances, where a bus's daily total was typically about 2.7% off and 9 in 10 were within 7.1%.

**Up-front cost: about CAD 21.5 billion (21,479,104,580)**
- **Buses:** 13,603 electric buses, each with its own charger. That includes 5,559 extra buses, because some daily schedules are too long for one winter charge.
- **Price:** each bus is priced at CAD 1,578,998 including its charger. This is Halifax's 2022 contract for 60 buses (*Award – RFP 21-021*, Halifax Regional Council, 17 May 2022, p. 2, https://www.halifax.ca/media/77822).
- **Not included:** grid upgrades and spare buses.
- All figures are in Canadian dollars, using a Canadian price rather than a London one.

**Yearly running costs** (both fuel prices are placeholders, not published figures)
| | Per year (CAD) |
|---|---|
| Electricity (placeholder price: CAD 0.15/kWh) | 119,318,676 |
| Diesel (placeholder price: CAD 1.70/L) | 357,807,322 |
| **Energy saving** | **238,488,646** |

**CO₂ saved: about 559,863 tonnes a year**
- **Diesel use:** 0.46 litres per km, the Irish urban bus average for 2018 (*Report on Diesel and Alternative-Fuel Bus Trials*, Irish Department of Transport, Dec 2019, p. 24, https://www.gov.ie/en/publication/7251e2-low-emission-bus-trials-report/).
- **CO₂ per litre:** 2.66 kg from the exhaust (*Learn the facts: Fuel consumption and CO2*, Natural Resources Canada, p. 2, https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/fuel-efficient-technologies/autosmart_factsheet_6_e.pdf).
- **Not subtracted:** emissions from generating the electricity, so the true net saving would be lower.

**Other assumptions**
- **Yearly distance:** 457,554,120 km, which is the hardest day's distance multiplied by 300 service days. The 300 days is a **placeholder**.
- Distance counts only trips carrying passengers, not empty runs to and from the garage.
- **Battery:** 400 kWh, of which 285 kWh is usable (71.25%). This comes from a Toronto transit (TTC) trial (*TTC's Green Bus Program: Final Results*, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14).
- **Winter energy use:** 1.7385 kWh per km. That is the TTC summer figure of 1.22 kWh/km raised 42.5%, based on a Finnish study finding winter use 40–45% higher (Vehviläinen et al., *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, Applied Sciences 2022, p. 1, https://www.mdpi.com/2076-3417/12/6/2762).
- The winter rate is applied all year, which overstates electricity cost for the warmer months.
- Each bus is assumed to charge once overnight with no charging during the day, which drives the extra-bus count.

**Overall:** the bus price, battery, energy use, diesel use and CO₂ factor are all from published sources. The electricity price, diesel price and 300 service days are placeholders, so the yearly cost and saving figures are the least reliable part.

---

## 8

**Agency:** london

**Question:** Roughly what would electrifying London (TfL buses)'s buses cost, and how much CO2 would it save each year? Assume winter energy use.

**Key tool numbers:**

- `get_cost_and_co2({"agency": "london", "season": "winter"})`: design_day: 2026-10-22, season: winter, currency: CAD, electric_buses_priced: 13603, of_which_extra_buses: 5559, chargers: 13603, capital_cost: 21479104580, annual_km: 457554120, annual_electricity_cost: 119318676, annual_diesel_cost: 357807322, annual_energy_saving: 238488646, annual_co2_saved_tonnes: 559863.2

**Answer:**

**Winter-energy estimate for London (TfL buses), design day 2026-10-22. These are crude, order-of-magnitude figures.**

**Capital cost: about CAD 21.5 billion** (21,479,104,580).
- This covers 13,603 electric buses. Of those, 5,559 are extra buses needed because some blocks are longer than one charge can cover.
- The price is CAD 1,578,998 per bus, which includes its charger. It comes from the Halifax Regional Council report "Award – RFP 21-021" (17 May 2022, p. 2, https://www.halifax.ca/media/77822). It is a sourced value.
- Grid upgrades and spare buses are not included.

**Annual CO2 saved: about 559,863 tonnes.**
- Method: diesel litres not burned × 2.66 kg CO2 per litre. The 2.66 comes from Natural Resources Canada, AutoSmart factsheet 6, p. 2 (https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/fuel-efficient-technologies/autosmart_factsheet_6_e.pdf).
- Diesel use is 0.46 L/km. It comes from the Irish Department of Transport bus trials report (Dec 2019, p. 24).
- Emissions from generating the electricity are not subtracted.

**Annual energy cost, which the tool also returned:**
- Electricity costs about CAD 119.3 million a year.
- Diesel costs about CAD 357.8 million a year.
- The energy saving is about CAD 238.5 million a year.
- These rest on **placeholder** prices: electricity at CAD 0.15/kWh and diesel at CAD 1.70/L. No published price was available.

**Other assumptions:**
- Annual distance is 457,554,120 km. It is the design-day distance × **300 service days, which is a placeholder**.
- Winter energy use is 1.7385 kWh/km. This is the TTC summer figure scaled up using the Finnish winter study (Vehviläinen et al., Applied Sciences 12(6) 2762, 2022, https://www.mdpi.com/2076-3417/12/6/2762).
- The battery is 400 kWh with 71.25% usable (285 kWh). It comes from the TTC Green Bus Program report, p. 55.
- Each bus has one overnight charge and one charger, with no daytime charging.

**Data caveats:**
- Distances are **ESTIMATED**. They are straight lines between stops multiplied by a road factor of 1.1183, which was calibrated on Dublin data.
- Blocks are **INFERRED**. The tool assumes a bus takes the next trip from the same terminal, with no interlining between routes. Treat all figures as approximate.
- Revenue km only, so deadhead running is excluded.
- The figures come from feed london_uk.zip version 20261020_032409. The timetable covers 2026-10-22 to 2026-11-18.

I haven't calculated payback, because that would need derived financial figures the tools don't provide.

---

## 9

**Agency:** halifax

**Question:** How many electric buses would Halifax Transit need in winter, compared with today, and what is the replacement ratio?

**Key tool numbers:**

- `get_fleet_size({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, season: winter, range_km: 163.9, blocks_in_service: 461, buses_needed_today: 284, blocks_over_range: 130, pct_over_range: 28.2, electric_buses_needed: 414, replacement_ratio: 1.458, benchmark_ratio: 1.2
- `get_design_day({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, same_pattern_dates: 10, rule: most blocks over range, then most blocks in service, then earliest date, blocks_over_range: 130, season: winter, range_km: 163.9, total_blocks: 461, within_range: 331, exceeding_range: 130, pct_within_range: 71.8, pct_exceeding_range: 28.2

**Answer:**

## Halifax Transit — winter fleet requirement

**Headline figures** (design day, winter energy use):

| | |
|---|---|
| Buses needed today | **284** |
| Electric buses needed | **414** |
| Replacement ratio (electric / today) | **1.458** |
| Benchmark ratio for comparison | 1.2 (PLACEHOLDER) |

So Halifax Transit would need roughly **414 electric buses in winter versus 284 buses today** — a replacement ratio of about **1.46 electric buses for every bus in service today**, well above the 1:1.2 planning benchmark. The benchmark is a PLACEHOLDER — the tool notes it is a commonly quoted planning figure, not something found in the source index.

**Why the fleet grows**

- The winter range is **163.9 km** per bus on one charge (400 kWh nominal battery × 0.7125 usable = 285 kWh usable, at 1.7385 kWh/km).
- On the design day **461 blocks** are in service; **331 (71.8%)** fit within that range and **130 (28.2%)** exceed it.
- Each block over range needs one extra bus, which is how the tool arrives at 414 (method: buses today = the most blocks in service at the same moment; each over-range block gets a fresh bus swapping in mid-day). **Spare buses are not included**, so this is a floor, not a complete fleet plan.

**The design day**

The hardest winter day is **2026-08-24**, and its pattern is shared by 10 dates in the feed (examples: 2026-08-24 through 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-25, 2026-10-23). The five longest blocks that day are 457.5 km (block 722134), 364.8 km (722151), 363.5 km (722165), 363.2 km (722252) and 363.0 km (712134) — all far beyond a single charge.

**Data provenance and caveats**

- Feed: **halifax.zip version 2026_08_August_20260806, sha256 f5d95091c813**, covering 2026-08-24 to 2026-11-29; summary built 2026-10-22.
- Distances here are **exact**, not estimated (shape_dist_traveled in stop_times.txt) and blocks are **published** block_ids from the feed, not inferred.
- Distances are **revenue km only** — deadhead to and from the garage is excluded, which makes the range check optimistic. The model assumes **one overnight charge and no daytime charging**.

**Sources for the assumptions**

- Battery: 400 kWh New Flyer 40-ft battery, and 285/400 kWh usable (0.7125) measured in service — TTC, *TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14 (SOURCED).
- Winter energy use: 1.22 kWh/km (TTC summer) × 1.425 = **1.7385 kWh/km**, the midpoint of the Finnish finding that winter use is 40–45% higher than summer — Vehviläinen et al., *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, Applied Sciences 12(6) 2762, 2022, p. 1, https://www.mdpi.com/2076-3417/12/6/2762 (SOURCED). TTC's own winter figure of 1.40 (p. 55) was not used because those New Flyer buses also burned diesel for heating (pp. 47, 61).
- The 1.2 benchmark ratio is a **PLACEHOLDER**.

---

## 10

**Agency:** dublin

**Question:** How long is block 5828_7778022_100220 in service on 6 January 2027?

**Key tool numbers:**

- `get_block_duration({"agency": "dublin", "block_id": "5828_7778022_100220", "date": "2027-01-06"})`: Block 5828_7778022_100220 is in service for 12 h 25 min on 2027-01-06.

**Answer:**

Block 5828_7778022_100220 is in service for 12 hours 25 minutes on 6 January 2027. That runs from the first trip's first departure to the last trip's last arrival. It includes layovers between trips. It leaves out the garage pull-out and pull-in.

The tool didn't say whether the block was inferred or the times estimated, and it gave no data snapshot, so I can't name the feed version.

---

## 11

**Agency:** halifax

**Question:** According to published sources, how many kilograms of CO2 does burning a litre of diesel release?

**Key tool numbers:**

- `search_sources({"query": "diesel CO2 emission factor kg per litre", "k": 5})`: Learn the facts: Fuel consumption and CO2 (AutoSmart factsheet 6) (Natural Resources Canada, 2); Report on Diesel and Alternative-Fuel Bus Trials (Department of Transport, Tourism and Sport (Ireland), 37); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 11); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 16); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 11)

**Answer:**

Natural Resources Canada says burning one litre of diesel releases **2.66 kg of CO2** at the tailpipe.

The same source gives these figures for other fuels:
- B5 biodiesel blend: 2.65 kg per litre
- B20 biodiesel blend: 2.62 kg per litre
- Gasoline: 2.29 kg per litre

Source: Natural Resources Canada, "Learn the facts: Fuel consumption and CO2" (AutoSmart factsheet 6), 2014, p. 2. https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/oee/pdf/transportation/fuel-efficient-technologies/autosmart_factsheet_6_e.pdf

---

## 12

**Agency:** dublin

**Question:** How many Dublin (Dublin Bus and Go-Ahead Ireland) blocks could run on one overnight charge in winter on 24 November 2026?

**Key tool numbers:**

- `get_fleet_feasibility({"agency": "dublin", "date": "2026-11-24", "season": "winter"})`: service_date: 2026-11-24, season: winter, range_km: 163.9, total_blocks: 1915, within_range: 1391, exceeding_range: 524, pct_within_range: 72.6, pct_exceeding_range: 27.4

**Answer:**

On Tuesday 24 November 2026, **1,391 of 1,915 Dublin blocks (72.6%)** could run a winter day on one overnight charge. The other **524 blocks (27.4%)** drive further than one charge allows.

**How range was worked out**
- **Winter range: 163.9 km per charge.** This comes from 285 kWh of usable battery divided by 1.7385 kWh used per km.
- **Battery: 400 kWh, of which 71.25% (285 kWh) is usable.** Both figures were measured on a New Flyer 40-ft bus in the Toronto trial. Source: TTC, *TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14
- **Winter energy use: 1.7385 kWh/km.** This is TTC's summer figure of 1.22 kWh/km multiplied by 1.425. The 1.425 is the middle of a Finnish finding that buses use 40–45% more energy in winter. Source: Vehviläinen et al., *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, Applied Sciences 12(6) 2762, 2022, p. 1, https://www.mdpi.com/2076-3417/12/6/2762
  - TTC's own winter figure (1.40 kWh/km, p. 55) wasn't used because those buses also burned diesel for heating.

**The longest blocks that day**
| Block | km |
|---|---|
| 5828_7778022_104090 | 412.4 |
| 5828_7778022_104030 | 396.7 |
| 5828_7778022_105070 | 381.6 |
| 5828_7778022_100390 | 373.3 |
| 5828_7778022_103280 | 370.4 |

The longest is about 2.5 times the winter range.

**Why 72.6% is an optimistic figure**
- **Only passenger-carrying km are counted.** Empty running to and from the garage is left out, so real daily distances are longer. Some blocks counted as fitting may actually go over the range.
- **No daytime charging is assumed.** Each bus gets one charge overnight and nothing during the day.

**Where the data comes from**
- The figures use the Dublin Bus and Go-Ahead Ireland timetables, feed version 7F45B939-88CD-4972-AC8A-1992A136F855, which covers 18 October 2026 to 30 January 2027.
- Distances were measured exactly from the route shapes in the timetable, not estimated.
- Blocks are the ones published in the timetable, not inferred.

---

## 13

**Agency:** london

**Question:** How far does block 7(14397040)-1 drive on 27 January 2027?

**Key tool numbers:**

- `get_block_distance({"agency": "london", "block_id": "7(14397040)-1", "date": "2027-01-27"})`: 2027-01-27 is outside the dates available for London (TfL buses): 2026-10-22 to 2026-11-18 (next 28 days from the build date).

**Answer:**

I can't give a distance for block 7(14397040)-1 on 27 January 2027. The London (TfL buses) timetable only covers 22 October 2026 to 18 November 2026. That is the 28 days from the build date, and 27 January 2027 falls outside it.

If you pick a date in that window, I'll run the lookup again. The result will be revenue km only, which leaves out empty running to and from the garage.

---

## 14

**Agency:** dublin

**Question:** How far does block 6000_7778195_3423024 drive on 23 October 2026?

**Key tool numbers:**

- `get_block_distance({"agency": "dublin", "block_id": "6000_7778195_3423024", "date": "2026-10-23"})`: Block 6000_7778195_3423024 does not run on 2026-10-23.
- `get_block_distance({"agency": "dublin", "block_id": "6000_7778195_3423024", "date": "2026-10-22"})`: Block 6000_7778195_3423024 does not run on 2026-10-22.
- `get_block_distance({"agency": "dublin", "block_id": "6000_7778195_3423024", "date": "2026-10-24"})`: Block 6000_7778195_3423024 does not run on 2026-10-24.
- `get_block_distance({"agency": "dublin", "block_id": "6000_7778195_3423024", "date": "2026-10-26"})`: Block 6000_7778195_3423024 does not run on 2026-10-26.

**Answer:**

**No distance figure is available for that block on 23 October 2026.**

The tool returns: *"Block 6000_7778195_3423024 does not run on 2026-10-23."* I also checked the surrounding days (22, 24 and 26 October 2026) and got the same result for each, so this isn't a single-date gap.

What this means:

- The timetable for Dublin (Dublin Bus and Go-Ahead Ireland) does not contain any trips for that block id on that date, so there is no distance to report. I can't give you a kilometres figure for it.
- A likely explanation is that the block id isn't in the format Dublin's blocks use (the tool's examples are numeric ids such as "722145" or ids like "25-3"), but the tool only tells me the block doesn't run — it doesn't confirm whether the id itself is unknown, so I can't say for certain which of those it is.

If you can give me a block id as it appears in the Dublin timetable, or tell me a route/service you're interested in, I can look up the distance (revenue km only) and, if useful, the time in service for that date. Note that the block distance tool returns revenue kilometres only — empty running to and from the garage is not included — and it flags when a distance is estimated or a block inferred.

---

## 15

**Agency:** dublin

**Question:** How much energy and peak depot power would Dublin (Dublin Bus and Go-Ahead Ireland)'s electric fleet need to charge overnight in winter?

**Key tool numbers:**

- `get_charging_needs({"agency": "dublin", "season": "winter"})`: design_day: 2026-10-19, season: winter, blocks_in_service: 1951, daily_km: 211344.3, overnight_energy_kwh: 367422.1, overnight_energy_mwh: 367.42, charging_window_hours: 6, peak_depot_power_kw: 61237.0, peak_depot_power_mw: 61.24

**Answer:**

In winter, Dublin's electric fleet would need about **367 MWh of energy each night**. If every bus charged at the same time over 6 hours, the depot would need about **61 MW of peak power**. Both are rough, low-end figures.

**Results (winter design day: 2026-10-19)**
- Blocks in service: 1,951
- Distance driven that day: 211,344.3 km
- **Energy needed overnight: 367,422 kWh (367.42 MWh)**
- **Peak depot power: 61,237 kW (61.24 MW)**, with the energy spread evenly over a 6-hour window and all buses charging at once

The design day is the hardest service day in the timetable for battery-electric buses.

**How the tool calculated it**
- Energy = the total km of all blocks that day × energy use per km.
- Peak power = that energy ÷ the charging window.
- Some blocks are longer than one charge's range. Their full energy is counted anyway, even though one battery couldn't hold it.

**Assumptions and sources**
- **Winter energy use, 1.7385 kWh/km (sourced):** the summer figure of 1.22 kWh/km from the Toronto (TTC) trial × 1.425. The 1.425 is the midpoint of a Finnish finding that buses use 40–45% more energy in winter. Source: Vehviläinen et al., *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, Applied Sciences 12(6) 2762, 2022, p. 1, https://www.mdpi.com/2076-3417/12/6/2762. TTC's own winter figure (1.40 kWh/km, p. 55) wasn't used because its test buses also burned diesel for heating.
- **Battery, 400 kWh with 285 kWh usable (71.25%) (sourced):** TTC, *TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14. This sets each bus's range but doesn't change the energy total.
- **6-hour charging window: placeholder.** It's an assumption, not taken from a source. A longer window would lower the peak power and a shorter one would raise it.

**Why the real figures would be higher**
- Only km driven with passengers are counted. Empty trips to and from the garage are left out, so actual energy and power needs would be higher.
- The tool assumes one overnight charge and no charging during the day.
- It assumes no smart charging that staggers buses across the night. That kind of scheduling could lower the peak.

**Data:** Dublin Bus and Go-Ahead Ireland timetable feeds, both version 7F45B939-88CD-4972-AC8A-1992A136F855, covering 2026-10-18 to 2027-01-30. Distances come from the feed's own route lengths and blocks are the ones the feed publishes, so the figures are exact, not estimated.

---

## 16

**Agency:** london

**Question:** How many London (TfL buses) blocks could run on one overnight charge in summer on 13 November 2026?

**Key tool numbers:**

- `get_fleet_feasibility({"agency": "london", "date": "2026-11-13", "season": "summer"})`: service_date: 2026-11-13, season: summer, range_km: 233.6, total_blocks: 9123, within_range: 7994, exceeding_range: 1129, pct_within_range: 87.6, pct_exceeding_range: 12.4

**Answer:**

**7,994 of 9,123 London (TfL buses) blocks — 87.6% — could run on one overnight charge** in summer conditions on 13 November 2026 (the remaining 1,129 blocks, 12.4%, would exceed one charge).

**Method and assumptions (from the tool):**
- Range used: **233.6 km** = 400 kWh nominal battery × 71.25% usable (285 kWh usable) ÷ 1.22 kWh/km.
  - Battery and usable fraction: SOURCED — *TTC's Green Bus Program: Final Results of TTC's Head-to-Head eBus Evaluation*, Toronto Transit Commission, p. 55, https://www.ttc.ca/All-public-meetings/board/2022/Board-Meeting-Apr-14 (New Flyer 40-ft, 400 kWh; 285/400 kWh usable measured in service).
  - Energy use 1.22 kWh/km: SOURCED — same TTC report, p. 55 (New Flyer 2021 in-service average).
- Assumes **one overnight charge, no daytime charging**, and counts **revenue km only** (garage deadheading excluded), so the share within range is optimistic.

**Five longest blocks that day:** A10-1 and A10-2 (376.6 km each), A10-3 and A10-4 (351.5 km each), and 64-1 (336.4 km) — all well over the 233.6 km single-charge range.

**Data caveats:**
- Distances are **ESTIMATED** (straight lines between consecutive stops × a 1.1183 road factor calibrated on Dublin's exact stop-shape distances; median block error ~2.7%, 90th percentile ~7.1%).
- Blocks are **INFERRED** (a bus arriving at a terminal takes the next trip departing there ≥5 minutes later; no interlining between routes).
- Figures come from feed **london_uk.zip version 20261020_032409** (timetable covering 2026-10-22 to 2026-11-18; the 28 days from the build date are built).

So treat 7,994 / 87.6% as approximate, and note it is a summer-energy figure for a mid-November service date.

---

## 17

**Agency:** halifax

**Question:** How far does block 722241 drive on 29 August 2026?

**Key tool numbers:**

- `get_block_distance({"agency": "halifax", "block_id": "722241", "date": "2026-08-29"})`: Block 722241 does not run on 2026-08-29.

**Answer:**

Block **722241** does not run on **29 August 2026** — the timetable tool returned no service for that block on that date, so there is no distance to report.

A couple of possibilities worth noting, without guessing at numbers:

- The block ID may be valid on a different service date (the ID format matters — e.g. Halifax blocks can be numbered like "25-3" or "722145"). I can look it up again if you give me another date, or check a different block ID.
- 29 August 2026 may fall on a date pattern where this block simply isn't scheduled.

If you'd like, I can:
- try the same block on a nearby date, or
- run the **design day** check for Halifax to find which service pattern is the hardest one to electrify, or
- look up a different block's distance for that date.

Just tell me which and I'll pull it from the tools.

---

## 18

**Agency:** halifax

**Question:** How much energy and peak depot power would Halifax Transit's electric fleet need to charge overnight in winter?

**Key tool numbers:**

- `get_charging_needs({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, season: winter, blocks_in_service: 461, daily_km: 52983.0, overnight_energy_kwh: 92110.9, overnight_energy_mwh: 92.11, charging_window_hours: 6, peak_depot_power_kw: 15351.8, peak_depot_power_mw: 15.35
- `get_design_day({"agency": "halifax", "season": "winter"})`: design_day: 2026-08-24, same_pattern_dates: 10, rule: most blocks over range, then most blocks in service, then earliest date, blocks_over_range: 130, season: winter, range_km: 163.9, total_blocks: 461, within_range: 331, exceeding_range: 130, pct_within_range: 71.8, pct_exceeding_range: 28.2
- `search_sources({"query": "Halifax Transit electric bus charging depot power garage", "k": 5})`: Award - RFP 21-021: Supply and Deliver up to Sixty 40 Foot Battery Electric Transit Buses and Chargers (Halifax Regional Council report, 2); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 13); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 14-15); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 14-15); Financial Analysis of Battery Electric Transit Buses (National Renewable Energy Laboratory (US Department of Energy), 15)
- `search_sources({"query": "bus depot charger power rating kW electric bus charging", "k": 5})`: Financial Analysis of Battery Electric Transit Buses (National Renewable Energy Laboratory (US Department of Energy), 15); Report on Diesel and Alternative-Fuel Bus Trials (Department of Transport, Tourism and Sport (Ireland), 37); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 14-15); Financial Analysis of Battery Electric Transit Buses (National Renewable Energy Laboratory (US Department of Energy), 15); Financial Analysis of Battery Electric Transit Buses (National Renewable Energy Laboratory (US Department of Energy), 21)
- `search_sources({"query": "winter energy use electric bus heating kWh per km", "k": 5})`: Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 12); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 16); Setting Up and Operating Electric City Buses in Harsh Winter Conditions (Vehviläinen et al., Applied Sciences 12(6), 2762 (MDPI), 16); Report on Diesel and Alternative-Fuel Bus Trials (Department of Transport, Tourism and Sport (Ireland), 37); Financial Analysis of Battery Electric Transit Buses (National Renewable Energy Laboratory (US Department of Energy), 15)

**Answer:**

### Context from the published sources (not inputs to the figures above)

**The winter assumption looks conservative.** The tool's 1.7385 kWh/km is built as a 42.5% uplift on a summer baseline. The underlying Finnish study's own measured numbers are starker: over ~500,000 km of operation, average consumption in *thermal winter* was **2.1 kWh/km** versus **1.2 kWh/km in thermal summer**, with the worst cold weeks reaching **almost 2.5 kWh/km** and a floor of roughly **1.1 kWh/km** in the best summer case — Vehviläinen et al., *Setting Up and Operating Electric City Buses in Harsh Winter Conditions*, p. 12 and p. 16, https://www.mdpi.com/2076-3417/12/6/2762. Its condition table (p. 12) shows medians of 1.9 kWh/km at temperatures below 0 °C and when snowing more than 1 cm/h in the 2020–21 season, and 1.6 kWh/km at −1 to −10 °C with snow melt. So on this source's evidence, a Halifax winter night could require materially more than 92.1 MWh and more than 15.35 MW. Related point from the same source: it also warns that snow build-up on charging tracks defeated pantograph alignment tolerances without extra measures such as a defrost system (pp. 13–15) — relevant to charger reliability, not energy.

**For scale on the power figure:** NREL's example US bus depot had an average daily peak demand of about **800 kW** and a monthly peak up to about **1,100 kW** *before* battery-electric buses were added (NREL, *Financial Analysis of Battery Electric Transit Buses*, p. 21, https://afdc.energy.gov/files/u/publication/financial_analysis_be_transit_buses.pdf). That gives some sense of how large the 15.35 MW incremental load is against an existing depot.

**Charger hardware context:** NREL's baseline has a depot charger at **$50,000 plus $17,050 installation, one per bus** (p. 15, same URL). Separately, Halifax Regional Council's May 2022 award to Nova Bus covered **up to 60 forty-foot battery-electric buses with chargers** for **$94,739,857 CAD net HST, 30 in 2022/23 and 30 in 2023/24** — Council report *Award – RFP 21-021*, p. 2, https://www.halifax.ca/media/77822. Note the 461 blocks in service on this design day is far more than those 60 buses, so that contract is not a fleet-wide figure.

### What I can't tell you

- **The 6-hour charging window is a PLACEHOLDER**, not a sourced figure. Because peak power is inversely proportional to the window, a different window would give a different MW — I can't tell you Halifax's actual depot window.
- **No Halifax-specific winter energy-use measurement** appears in the index; the winter kWh/km is borrowed from a Finnish study via a TTC summer baseline.
- The figures exclude deadhead, so they are a floor, not a realistic design value.

---

## 19

**Agency:** london

**Question:** Give me the distance and the service time for block 79-6 on 9 November 2026.

**Key tool numbers:**

- `get_block_distance({"agency": "london", "block_id": "79-6", "date": "2026-11-09"})`: Block 79-6 drives 201.5 revenue km on 2026-11-09. [distance ESTIMATED from straight lines between stops x road factor 1.1183; block INFERRED by chaining trips at terminals]
- `get_block_duration({"agency": "london", "block_id": "79-6", "date": "2026-11-09"})`: Block 79-6 is in service for 17 h 51 min on 2026-11-09. [distance ESTIMATED from straight lines between stops x road factor 1.1183; block INFERRED by chaining trips at terminals]

**Answer:**

Block 79-6 on 9 November 2026 drives **about 201.5 km** and is in service for **17 h 51 min**. Both figures are approximate.

- **Distance:** This counts only trips that carry passengers. Driving to and from the garage isn't included. The figure is an estimate: the tool measured straight lines between stops and multiplied by a road factor of 1.1183, so the real road distance may be different.
- **Service time:** This runs from the first trip's departure to the last trip's arrival. It includes layovers between trips but not driving to and from the garage.

**Caveat:** This block was pieced together by linking trips that end and start at the same terminal. London's timetable data doesn't give TfL blocks directly; they're approximated by operator. The real vehicle schedule could group these trips differently.

---

## 20

**Agency:** london

**Question:** How far does block C10-7 drive on 6 November 2026?

**Key tool numbers:**

- `get_block_distance({"agency": "london", "block_id": "C10-7", "date": "2026-11-06"})`: Block C10-7 drives 207.2 revenue km on 2026-11-06. [distance ESTIMATED from straight lines between stops x road factor 1.1183; block INFERRED by chaining trips at terminals]

**Answer:**

Block C10-7 drives an estimated **207.2 revenue km** on 6 November 2026.

This figure is approximate for two reasons:
- **Distance is estimated.** It comes from straight lines between stops, scaled by a road factor of 1.1183.
- **Block is inferred.** The trips were chained together at terminals, not taken from an official block assignment.

The figure counts only revenue km (trips carrying passengers). Empty running to and from the garage is not included, so the bus's total daily mileage will be higher.
