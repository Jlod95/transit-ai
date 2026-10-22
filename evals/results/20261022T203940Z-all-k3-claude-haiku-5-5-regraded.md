# Eval run: all, k=3

- timestamp: `2026-10-22T20:39:40Z`
- split: `all`
- k: `3`
- model: `claude-haiku-5-5`
- concurrency: `5`
- git_commit: `9f7eeaa`
- tasks_sha256: `6e24be959dcbd5f7ec3d94608100794927a728a5d896155aee4e32f18b81e5a7`
- sources_index_sha256: `50fa90fd2d7797859d69ec35b593a47c72803a2e245061306eee3f40b239da0a`
- regraded: `True`
- context: `saved with the run`
- summary dublin.json: `3388eadb751c`
- summary halifax.json: `fad5dfa62ae6`
- summary london.json: `cfcc403967f8`

**Pass rate: 86/90 attempts (96%)** · cost $0.11 · 8.4 min

## By check

| Check | Passed |
|---|---|
| steps | 90/90 |
| end_state | 90/90 |
| unsupported | 86/90 |

## By category

| Category | Attempts passed | pass@3 (tasks) | pass^3 (tasks) |
|---|---|---|---|
| abstain | 9/9 | 3/3 | 3/3 |
| block_both | 9/9 | 3/3 | 3/3 |
| block_distance | 9/9 | 3/3 | 3/3 |
| block_duration | 6/6 | 2/2 | 2/2 |
| charging | 6/6 | 2/2 | 2/2 |
| cost_co2 | 3/6 | 1/2 | 1/2 |
| design_day | 9/9 | 3/3 | 3/3 |
| feasibility_summer | 6/6 | 2/2 | 2/2 |
| feasibility_winter | 6/6 | 2/2 | 2/2 |
| fleet_size | 5/6 | 2/2 | 1/2 |
| not_running | 6/6 | 2/2 | 2/2 |
| outside_timetable | 6/6 | 2/2 | 2/2 |
| sources | 6/6 | 2/2 | 2/2 |
| **all** | 86/90 | 29/30 | 28/30 |

## Derived numbers (warnings, not failures): 5

- `halifax-09-cost_co2` #2: 19,450 (rounding to fewer significant figures, from 19449)
- `halifax-09-cost_co2` #3: 19,400 (rounding to fewer significant figures, from 19449)
- `london-05-cost_co2` #1: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #2: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #3: 560,000 (rounding to fewer significant figures, from 559863)

## Failures by check type

### steps (0)


### end_state (0)


### unsupported (4)

- `halifax-09-cost_co2` #1: unsupported numbers: 284
- `halifax-09-cost_co2` #2: unsupported numbers: 284
- `halifax-09-cost_co2` #3: unsupported numbers: 284
- `dublin-06-fleet_size` #1: unsupported numbers: 0.03

