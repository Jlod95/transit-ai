# Model benchmark: eval-v1 harness, all 30 tasks

pass@k: a task passes if any of its k attempts passes. pass^k: only if all k pass. Cost and latency are per attempt (one answered question).

## claude-haiku-5-5

Run `20261022T203940Z-all-k3-claude-haiku-5-5.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:39:40Z

| Split | Tasks | Attempts passed | pass@3 | pass^3 |
|---|---|---|---|---|
| dev (Halifax) | 14 | 39/42 | 13/14 | 13/14 |
| held-out (Dublin, London) | 16 | 41/48 | 15/16 | 12/16 |

| Failed attempts: steps | end state | unsupported numbers | Avg cost / attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|
| 0 | 0 | 10 | $0.0013 | 5.6 s | $0.11 |

<details><summary>Failure details</summary>

- `halifax-09-cost_co2` #1 unsupported: unsupported: 284
- `halifax-09-cost_co2` #2 unsupported: unsupported: 284
- `halifax-09-cost_co2` #3 unsupported: unsupported: 284
- `dublin-06-fleet_size` #1 unsupported: unsupported: 0.03
- `london-03-feasibility_summer` #2 unsupported: unsupported: 90
- `london-03-feasibility_summer` #3 unsupported: unsupported: 90
- `london-04-design_day` #1 unsupported: unsupported: 90
- `london-04-design_day` #2 unsupported: unsupported: 90
- `london-04-design_day` #3 unsupported: unsupported: 90
- `london-05-cost_co2` #2 unsupported: unsupported: 90

</details>

## claude-sonnet-5-5

Run `20261022T204134Z-all-k3-claude-sonnet-5-5.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:41:34Z

| Split | Tasks | Attempts passed | pass@3 | pass^3 |
|---|---|---|---|---|
| dev (Halifax) | 14 | 42/42 | 14/14 | 14/14 |
| held-out (Dublin, London) | 16 | 45/48 | 16/16 | 14/16 |

| Failed attempts: steps | end state | unsupported numbers | Avg cost / attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|
| 0 | 0 | 3 | $0.0213 | 6.1 s | $1.91 |

<details><summary>Failure details</summary>

- `london-03-feasibility_summer` #3 unsupported: unsupported: 90
- `london-04-design_day` #1 unsupported: unsupported: 90
- `london-04-design_day` #2 unsupported: unsupported: 90

</details>

## claude-opus-5-5

Run `20261022T204337Z-all-k3-claude-opus-5-5.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:43:37Z

| Split | Tasks | Attempts passed | pass@3 | pass^3 |
|---|---|---|---|---|
| dev (Halifax) | 14 | 41/42 | 14/14 | 13/14 |
| held-out (Dublin, London) | 16 | 43/48 | 16/16 | 12/16 |

| Failed attempts: steps | end state | unsupported numbers | Avg cost / attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|
| 0 | 2 | 4 | $0.0481 | 9.4 s | $4.33 |

<details><summary>Failure details</summary>

- `halifax-12-outside_timetable` #1 end_state: missing says the date isn't covered
- `dublin-04-feasibility_winter` #3 unsupported: unsupported: 2.5
- `london-03-feasibility_summer` #1 unsupported: unsupported: 90
- `london-03-feasibility_summer` #3 unsupported: unsupported: 90
- `london-04-design_day` #2 unsupported: unsupported: 90
- `london-07-outside_timetable` #3 end_state: missing says the date isn't covered

</details>
