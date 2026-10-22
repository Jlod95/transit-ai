# Eval run: all, k=3

- timestamp: `2026-10-22T23:12:39Z`
- split: `all`
- k: `3`
- model: `openrouter:deepseek/deepseek-v4.1-flash`
- concurrency: `5`
- git_commit: `570439b`
- tasks_sha256: `6e24be959dcbd5f7ec3d94608100794927a728a5d896155aee4e32f18b81e5a7`
- sources_index_sha256: `50fa90fd2d7797859d69ec35b593a47c72803a2e245061306eee3f40b239da0a`
- regraded: `True`
- context: `saved with the run`
- summary dublin.json: `3388eadb751c`
- summary halifax.json: `fad5dfa62ae6`
- summary london.json: `cfcc403967f8`

**Pass rate: 85/90 attempts (94%)** · cost $0.08 · 7.4 min

## By check

| Check | Passed |
|---|---|
| steps | 90/90 |
| end_state | 88/90 |
| unsupported | 87/90 |

## By category

| Category | Attempts passed | pass@3 (tasks) | pass^3 (tasks) |
|---|---|---|---|
| abstain | 9/9 | 3/3 | 3/3 |
| block_both | 9/9 | 3/3 | 3/3 |
| block_distance | 9/9 | 3/3 | 3/3 |
| block_duration | 6/6 | 2/2 | 2/2 |
| charging | 5/6 | 2/2 | 1/2 |
| cost_co2 | 5/6 | 2/2 | 1/2 |
| design_day | 8/9 | 3/3 | 2/3 |
| feasibility_summer | 6/6 | 2/2 | 2/2 |
| feasibility_winter | 6/6 | 2/2 | 2/2 |
| fleet_size | 6/6 | 2/2 | 2/2 |
| not_running | 4/6 | 2/2 | 0/2 |
| outside_timetable | 6/6 | 2/2 | 2/2 |
| sources | 6/6 | 2/2 | 2/2 |
| **all** | 85/90 | 30/30 | 25/30 |

## Derived numbers (warnings, not failures): 7

- `halifax-08-charging` #3: 42.5 (percent <-> fraction, from 1.425)
- `halifax-09-cost_co2` #2: 650 million (rounding to fewer significant figures, from 6.53705e+08)
- `halifax-09-cost_co2` #2: 19,400 (rounding to fewer significant figures, from 19449)
- `london-05-cost_co2` #1: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #2: 559,900 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #3: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #3: 560,000 (rounding to fewer significant figures, from 559863)

## Failures by check type

### steps (0)


### end_state (2)

- `halifax-06-design_day` #1: missing design day (2026-08-24)
- `london-05-cost_co2` #2: missing CO2 saved (t/yr) ([[559863.2]])

### unsupported (3)

- `halifax-08-charging` #3: unsupported numbers: −1, −10
- `halifax-11-not_running` #1: unsupported numbers: 25, 722145
- `dublin-08-not_running` #3: unsupported numbers: 722145, 25

