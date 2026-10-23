"""The judge's offline parts: Cohen's kappa and the answer selection (no API calls)."""

import pytest

from evals.judge import PICKS, RUNS, cohen_kappa, key_numbers


def test_kappa_perfect_chance_and_worked_example():
    assert cohen_kappa(list("YYNN"), list("YYNN")) == 1.0
    assert cohen_kappa(list("YNYN"), list("YYNN")) == 0.0  # agreement no better than chance
    # 10 items: both Y on 6, both N on 2, disagree on 2 (one each way).
    a = list("YYYYYYNNYN")
    b = list("YYYYYYNNNY")
    # observed 0.8; expected 0.7*0.7 + 0.3*0.3 = 0.58; kappa = 0.22 / 0.42
    assert cohen_kappa(a, b) == pytest.approx(0.22 / 0.42)


def test_picks_cover_every_model_and_both_splits():
    assert len(PICKS) == 20 and {m for m, _, _ in PICKS} == set(RUNS)
    agencies = {t.split("-")[0] for _, t, _ in PICKS}
    assert agencies == {"halifax", "dublin", "london"}
    assert ("deepseek-v4.1-flash", "dublin-08-not_running", 3) in PICKS
    assert {("claude-opus-5-5", "london-02-block_both", 3), ("claude-opus-5-5", "london-05-cost_co2", 3)} <= set(PICKS)


def test_key_numbers_keeps_short_scalars():
    assert key_numbers('{"km": 80.5, "method": "' + "x" * 200 + '"}') == "km: 80.5"
    assert key_numbers("Block 1 drives 80.5 revenue km.") == "Block 1 drives 80.5 revenue km."
