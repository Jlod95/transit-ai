# Eval run: all, k=3

- timestamp: `2026-10-22T20:43:37Z`
- split: `all`
- k: `3`
- model: `claude-opus-5-5`
- concurrency: `5`
- git_commit: `9f7eeaa`
- tasks_sha256: `6e24be959dcbd5f7ec3d94608100794927a728a5d896155aee4e32f18b81e5a7`
- sources_index_sha256: `50fa90fd2d7797859d69ec35b593a47c72803a2e245061306eee3f40b239da0a`
- regraded: `True`
- context: `saved with the run`
- summary dublin.json: `3388eadb751c`
- summary halifax.json: `fad5dfa62ae6`
- summary london.json: `cfcc403967f8`

**Pass rate: 87/90 attempts (97%)** · cost $4.33 · 14.2 min

## By check

| Check | Passed |
|---|---|
| steps | 90/90 |
| end_state | 88/90 |
| unsupported | 89/90 |

## By category

| Category | Attempts passed | pass@3 (tasks) | pass^3 (tasks) |
|---|---|---|---|
| abstain | 9/9 | 3/3 | 3/3 |
| block_both | 9/9 | 3/3 | 3/3 |
| block_distance | 9/9 | 3/3 | 3/3 |
| block_duration | 6/6 | 2/2 | 2/2 |
| charging | 6/6 | 2/2 | 2/2 |
| cost_co2 | 6/6 | 2/2 | 2/2 |
| design_day | 9/9 | 3/3 | 3/3 |
| feasibility_summer | 6/6 | 2/2 | 2/2 |
| feasibility_winter | 5/6 | 2/2 | 1/2 |
| fleet_size | 6/6 | 2/2 | 2/2 |
| not_running | 6/6 | 2/2 | 2/2 |
| outside_timetable | 4/6 | 2/2 | 0/2 |
| sources | 6/6 | 2/2 | 2/2 |
| **all** | 87/90 | 30/30 | 27/30 |

## Derived numbers (warnings, not failures): 13

- `halifax-05-feasibility_winter` #2: 42.5 (percent <-> fraction, from 1.425)
- `halifax-05-feasibility_winter` #3: 42.5 (percent <-> fraction, from 1.425)
- `halifax-06-design_day` #2: 42.5 (percent <-> fraction, from 1.425)
- `halifax-07-fleet_size` #2: 42.5 (percent <-> fraction, from 1.425)
- `halifax-09-cost_co2` #1: 19,400 (rounding to fewer significant figures, from 19449)
- `halifax-09-cost_co2` #1: 42.5 (percent <-> fraction, from 1.425)
- `halifax-09-cost_co2` #2: 19,400 (rounding to fewer significant figures, from 19449)
- `halifax-09-cost_co2` #3: 42.5 (percent <-> fraction, from 1.425)
- `dublin-07-charging` #2: 42.5 (percent <-> fraction, from 1.425)
- `london-05-cost_co2` #1: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #2: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #3: 560,000 (rounding to fewer significant figures, from 559863)
- `london-05-cost_co2` #3: 42.5 (percent <-> fraction, from 1.425)

## Failures by check type

### steps (0)


### end_state (2)

- `halifax-12-outside_timetable` #1: missing says the date isn't covered (phrase)
- `london-07-outside_timetable` #3: missing says the date isn't covered (phrase)

### unsupported (1)

- `dublin-04-feasibility_winter` #3: unsupported numbers: 2.5

