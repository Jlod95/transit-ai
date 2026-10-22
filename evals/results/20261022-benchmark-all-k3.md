# Model benchmark: all 30 tasks

pass@k: a task passes if any of its k attempts passes. pass^k: only if all k pass. Cost and latency are per attempt (one answered question). Re-graded runs show the grade under every grader version (v1, v1.1, v1.2) side by side; the answers are the same. Disclosure (v1.2, not part of the pass): London answers built on tool output flagged ESTIMATED / INFERRED must say distances are estimated and blocks inferred; shown as passed/applicable attempts. Cost per passed attempt = total cost / attempts passed.

| Model | v1: attempts passed · pass^3 | v1.1: attempts passed · pass^3 | v1.2: attempts passed · pass^3 | Disclosure (v1.2, separate) | Cost / attempt | Cost / passed attempt (v1.2) | Total cost |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 80/90 · 25/30 | 86/90 · 28/30 | 86/90 · 28/30 | 15/15 | $0.0013 | $0.0013 | $0.11 |
| claude-sonnet-5-5 | 87/90 · 28/30 | 90/90 · 30/30 | 90/90 · 30/30 | 15/15 | $0.0213 | $0.0213 | $1.91 |
| claude-opus-5-5 | 84/90 · 25/30 | 87/90 · 27/30 | 89/90 · 29/30 | 13/15 | $0.0481 | $0.0486 | $4.33 |
| openrouter:deepseek/deepseek-v4.1-flash | 83/90 · 24/30 | 85/90 · 25/30 | 87/90 · 27/30 | 15/15 | $0.0009 | $0.0010 | $0.08 |

## claude-haiku-5-5

Run `20261022T203940Z-all-k3-claude-haiku-5-5-regraded.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:39:40Z

| Split | Tasks | v1 attempts | v1 pass@3 | v1 pass^3 | v1.1 attempts | v1.1 pass@3 | v1.1 pass^3 | v1.2 attempts | v1.2 pass@3 | v1.2 pass^3 |
|---|---|---|---|---|---|---|---|---|---|---|
| dev (Halifax) | 14 | 39/42 | 13/14 | 13/14 | 39/42 | 13/14 | 13/14 | 39/42 | 13/14 | 13/14 |
| held-out (Dublin, London) | 16 | 41/48 | 15/16 | 12/16 | 47/48 | 16/16 | 15/16 | 47/48 | 16/16 | 15/16 |

| Failed attempts (v1.2): steps | end state | unsupported numbers | Avg cost / attempt | Cost / passed attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|---|
| 0 | 0 | 4 | $0.0013 | $0.0013 | 5.6 s | $0.11 |

<details><summary>Failure details (v1.2)</summary>

- `halifax-09-cost_co2` #1 unsupported: unsupported: 284
- `halifax-09-cost_co2` #2 unsupported: unsupported: 284
- `halifax-09-cost_co2` #3 unsupported: unsupported: 284
- `dublin-06-fleet_size` #1 unsupported: unsupported: 0.03

</details>

## claude-sonnet-5-5

Run `20261022T204134Z-all-k3-claude-sonnet-5-5-regraded.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:41:34Z

| Split | Tasks | v1 attempts | v1 pass@3 | v1 pass^3 | v1.1 attempts | v1.1 pass@3 | v1.1 pass^3 | v1.2 attempts | v1.2 pass@3 | v1.2 pass^3 |
|---|---|---|---|---|---|---|---|---|---|---|
| dev (Halifax) | 14 | 42/42 | 14/14 | 14/14 | 42/42 | 14/14 | 14/14 | 42/42 | 14/14 | 14/14 |
| held-out (Dublin, London) | 16 | 45/48 | 16/16 | 14/16 | 48/48 | 16/16 | 16/16 | 48/48 | 16/16 | 16/16 |

| Failed attempts (v1.2): steps | end state | unsupported numbers | Avg cost / attempt | Cost / passed attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | $0.0213 | $0.0213 | 6.1 s | $1.91 |

<details><summary>Failure details (v1.2)</summary>

- none

</details>

## claude-opus-5-5

Run `20261022T204337Z-all-k3-claude-opus-5-5-regraded.json` · commit `9f7eeaa` · k=3 · 2026-10-22T20:43:37Z

| Split | Tasks | v1 attempts | v1 pass@3 | v1 pass^3 | v1.1 attempts | v1.1 pass@3 | v1.1 pass^3 | v1.2 attempts | v1.2 pass@3 | v1.2 pass^3 |
|---|---|---|---|---|---|---|---|---|---|---|
| dev (Halifax) | 14 | 41/42 | 14/14 | 13/14 | 41/42 | 14/14 | 13/14 | 42/42 | 14/14 | 14/14 |
| held-out (Dublin, London) | 16 | 43/48 | 16/16 | 12/16 | 46/48 | 16/16 | 14/16 | 47/48 | 16/16 | 15/16 |

| Failed attempts (v1.2): steps | end state | unsupported numbers | Avg cost / attempt | Cost / passed attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|---|
| 0 | 0 | 1 | $0.0481 | $0.0486 | 9.4 s | $4.33 |

<details><summary>Failure details (v1.2)</summary>

- `dublin-04-feasibility_winter` #3 unsupported: unsupported: 2.5
- `london-02-block_both` #3 disclosure (separate): doesn't say inferred
- `london-05-cost_co2` #3 disclosure (separate): doesn't say inferred

</details>

## openrouter:deepseek/deepseek-v4.1-flash

Run `20261022T231239Z-all-k3-openrouter-deepseek-v4.1-flash-regraded.json` · commit `570439b` · k=3 · 2026-10-22T23:12:39Z

| Split | Tasks | v1 attempts | v1 pass@3 | v1 pass^3 | v1.1 attempts | v1.1 pass@3 | v1.1 pass^3 | v1.2 attempts | v1.2 pass@3 | v1.2 pass^3 |
|---|---|---|---|---|---|---|---|---|---|---|
| dev (Halifax) | 14 | 39/42 | 14/14 | 11/14 | 39/42 | 14/14 | 11/14 | 40/42 | 14/14 | 12/14 |
| held-out (Dublin, London) | 16 | 44/48 | 16/16 | 13/16 | 46/48 | 16/16 | 14/16 | 47/48 | 16/16 | 15/16 |

| Failed attempts (v1.2): steps | end state | unsupported numbers | Avg cost / attempt | Cost / passed attempt | Avg latency / attempt | Total cost |
|---|---|---|---|---|---|---|
| 0 | 0 | 3 | $0.0009 | $0.0010 | 5.0 s | $0.08 |

<details><summary>Failure details (v1.2)</summary>

- `halifax-08-charging` #3 unsupported: unsupported: -10
- `halifax-11-not_running` #1 unsupported: unsupported: 25, 722145
- `dublin-08-not_running` #3 unsupported: unsupported: 722145, 25

</details>
