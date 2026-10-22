"""The eval verifier on hand-written fake answers, so it is itself tested before it grades."""

from evals.verify import check_unsupported, parse_numbers, verify

TASK = {
    "id": "fake-block_both",
    "question": "Give me the distance and the service time for block 722145 on 14 October 2026.",
    "expected_calls": [
        {"name": "get_block_distance", "args": {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}},
        {"name": "get_block_duration", "args": {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}},
    ],
    "oracle": [
        {"type": "number", "label": "km", "accept": [[80.5]]},
        {"type": "number", "label": "duration", "accept": [[3, 16], [196]]},
    ],
    "ignore_tokens": ["722145"],
}
ARGS = {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}
DISTANCE = {"name": "get_block_distance", "input": ARGS,
            "result": "Block 722145 drives 80.5 revenue km on 2026-10-14."}
DURATION = {"name": "get_block_duration", "input": ARGS,
            "result": "Block 722145 is in service for 3 h 16 min on 2026-10-14."}


def test_correct_answer_passes():
    answer = ("On 14 October 2026, block 722145 drives **80.5 km** and is in service for "
              "3 h 16 min (first departure to last arrival).")
    checks = verify(TASK, {"answer": answer, "tool_calls": [DISTANCE, DURATION]})
    assert checks["pass"], checks


def test_wrong_number_fails_end_state_and_is_unsupported():
    answer = "Block 722145 drives 85.0 km on 14 October 2026 and is in service for 3 h 16 min."
    checks = verify(TASK, {"answer": answer, "tool_calls": [DISTANCE, DURATION]})
    assert not checks["pass"]
    assert [m["label"] for m in checks["end_state"]["missing"]] == ["km"]
    assert checks["unsupported"]["numbers"] == ["85.0"]
    assert checks["steps"]["pass"]


def test_invented_number_is_unsupported():
    # Both oracle numbers are right, but "140 kWh" came from nowhere.
    answer = ("Block 722145 drives 80.5 km and is in service for 3 h 16 min on 14 October 2026; "
              "that would use about 140 kWh.")
    checks = verify(TASK, {"answer": answer, "tool_calls": [DISTANCE, DURATION]})
    assert checks["end_state"]["pass"] and checks["steps"]["pass"]
    assert checks["unsupported"]["numbers"] == ["140"]
    assert not checks["pass"]


def test_missing_tool_call_fails_steps():
    answer = "Block 722145 drives 80.5 km on 14 October 2026."
    checks = verify(TASK, {"answer": answer, "tool_calls": [DISTANCE]})
    assert not checks["steps"]["pass"]
    assert checks["steps"]["missing"] == [{"name": "get_block_duration", "args": ARGS}]
    assert not checks["pass"]


def test_wrong_tool_argument_fails_steps():
    wrong_date = {**DISTANCE, "input": {**ARGS, "date": "2026-10-15"}}
    checks = verify(TASK, {"answer": "80.5 km, 3 h 16 min", "tool_calls": [wrong_date, DURATION]})
    assert checks["steps"]["missing"] == [{"name": "get_block_distance", "args": ARGS}]


def test_failed_run_fails_every_check():
    checks = verify(TASK, {"error": "APIConnectionError: offline"})
    assert not any(checks[c]["pass"] for c in ("steps", "end_state", "unsupported"))


def test_number_parsing_scales_and_units():
    values = {raw.strip(): (v, h) for v, h, _, raw in parse_numbers(
        "CA$654 million, 1,578,998 dollars, 17.7 MW and 71.8%")}
    assert values["654 million"] == (654e6, 0.5e6)  # rounded to the nearest million
    assert values["1,578,998"] == (1578998, 0.5)
    assert values["17.7"] == (17.7, 0.05)  # "MW" is a unit, not "M" for million
    assert values["71.8"] == (71.8, 0.05)


def test_dates_years_block_ids_and_small_counts_are_ignored():
    task = {**TASK, "ignore_tokens": ["722145", "25-1"]}
    answer = ("Blocks 722145 and 25-1 run on 14 October 2026 (2026-10-14) and Oct 15; by 2034 "
              "the fleet changes. The 5 longest blocks are listed.")
    assert check_unsupported(task, answer, [])["numbers"] == []


def test_abstention_passes_without_numbers():
    task = {"id": "fake-abstain", "question": "How much does a driver earn per hour?",
            "expected_calls": [],
            "oracle": [{"type": "phrase_any", "label": "says it can't answer",
                        "phrases": ["don't have", "can't"]}]}
    good = verify(task, {"answer": "I don't have wage data, so I can't answer that.", "tool_calls": []})
    assert good["pass"]
    invented = verify(task, {"answer": "I don't have exact data, but about $32 an hour.", "tool_calls": []})
    assert invented["unsupported"]["numbers"] == ["32"] and not invented["pass"]
