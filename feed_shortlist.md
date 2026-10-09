# GTFS feed shortlist

Checked on 2026-10-08 with `scripts/check_feed.py`. Feeds are saved in `data/raw/` (gitignored).
Fleet sizes are approximate public figures, not taken from the feeds; verify before quoting them.

| Agency | City | Approx. buses | Download URL | Licence / terms | Routes / trips | block_id coverage | Distance fields (`shape_dist_traveled`) | Notes |
|---|---|---|---|---|---|---|---|---|
| Halifax Transit | Halifax, NS, Canada | ~350 | http://gtfs.halifax.ca/static/google_transit.zip | [Open Government Licence – Halifax](https://data-hrm.hub.arcgis.com/pages/open-data-licence) (attribution required, commercial use allowed) | 81 / 9,239 | 100% | shapes 100%, stop_times 97.1% | Feed valid 2026-08-24 to 2026-11-29. Agency is actively buying battery-electric buses, which suits the project story. |
| Metro Transit | Madison, WI, USA | ~200 | http://transitdata.cityofmadison.com/GTFS/mmt_gtfs.zip | [Developer Licence Agreement and Terms of Use](https://www.cityofmadison.com/metro/business/information-for-developers/developer-license-agreement-and-terms-of-use) (custom terms; read before publishing) | 29 / 14,199 | 100% | shapes 100%, stop_times 100% | Feed valid 2026-08-16 to 2026-12-05. Most complete distance data of the set. |
| London Transit Commission | London, ON, Canada | ~230 | https://www.londontransit.ca/gtfsfeed/google_transit.zip | [LTC Open Data Terms of Use](https://www.londontransit.ca/open-data/ltcs-open-data-terms-of-use/) (royalty-free, non-exclusive) | 38 / 8,705 | 100% | Not present | Feed valid 2026-09-28 to 2026-11-28. Distances would have to be computed from shape geometry. |
| Nottingham City Transport | Nottingham, UK | ~330 | https://data.discoverpassenger.com/operator/nctx/dataset/current/download/gtfs | OGL-UK-3.0 (per [Mobility Database](https://mobilitydatabase.org/feeds/gtfs/mdb-1946); no `feed_info.txt` in the feed) | 101 / 11,131 | 99.6% | shapes column present but 0% filled; stop_times not present | Distances would have to be computed. No `feed_info.txt`, so licence and dates come from outside the feed. |
| Grand River Transit | Waterloo Region, ON, Canada | ~300 | https://webapps.regionofwaterloo.ca/api/grt-routes/api/staticfeeds/1 | [Region of Waterloo Open Data Licence v2.0](https://www.regionofwaterloo.ca/en/regional-government/open-data.aspx) | not checked | not checked | not checked | Download failed: connection timed out. The older URL returns 404. See "Manual download" below. |

## Recommendation

- **Demo feed: Halifax Transit.** Full block_id coverage, distances in both shapes and stop_times,
  a clear open licence that allows reuse with attribution, a mid-sized fleet, and a real
  electrification programme to compare against.
- **Backup: Madison Metro Transit.** The most complete data (100% on every field checked), but the
  terms are a custom agreement rather than a standard open licence, so read them before
  publishing anything built on it.

Things to double-check before relying on these numbers:
- Feeds expire. Every feed above ends between late November and early December 2026; re-download
  and re-run the check when you start real work.
- `shape_dist_traveled` units are not fixed by the GTFS spec (could be metres, km or miles).
  Compare against a known route length before using them for energy estimates.

## Manual download (Grand River Transit)

The automatic download timed out. To try by hand:
1. Open https://www.grt.ca/about-grt/open-data/ in a browser and find the GTFS static schedule link.
2. Save the zip as `data/raw/grt.zip`.
3. Run `python scripts/check_feed.py data/raw/grt.zip` and add the results to the table.
