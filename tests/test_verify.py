"""The eval verifier on hand-written fake answers, so it is itself tested before it grades."""

from evals.verify import check_disclosure, check_end_state, check_unsupported, parse_numbers, verify

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


def test_abstention_passes_without_invented_numbers():
    task = {"id": "fake-abstain", "question": "How much does a driver earn per hour?",
            "expected_calls": [],
            "oracle": [{"type": "no_invented_figure", "label": "gives no figure it wasn't given"}]}
    # Any wording passes, as long as no figure is made up.
    good = verify(task, {"answer": "Wages aren't something the timetable data covers.", "tool_calls": []})
    assert good["pass"]
    invented = verify(task, {"answer": "I don't have exact data, but about $32 an hour.", "tool_calls": []})
    assert not invented["end_state"]["pass"] and invented["unsupported"]["numbers"] == ["32"]


# --- Number levels: supported, derived (warning) and unsupported (fail) ---

COST_TASK = {"id": "fake-cost", "question": "What would electrifying cost, and what CO2 would it save?",
             "expected_calls": [], "oracle": []}
COST_CALL = {"name": "get_cost_and_co2", "input": {"agency": "halifax", "season": "winter"},
             "result": '{"capital_cost": 653705013, "annual_energy_saving": 8288042, '
                       '"annual_co2_saved_tonnes": 19449.0, "pct_within_range": 71.8, '
                       '"duration_minutes": 530}'}


def levels(answer, context=""):
    return check_unsupported(COST_TASK, answer, [COST_CALL], context)


def test_rounding_to_fewer_significant_figures_is_derived():
    result = levels("It saves about 19,400 tonnes of CO2 a year.")
    assert result["pass"] and result["numbers"] == []
    assert result["derived"] == [{"number": "19,400", "rule": "rounding to fewer significant figures",
                                  "from": 19449.0}]


def test_multiplier_as_percent_is_derived():
    # 1.425 (stated in the agent's context) -> "42.5%" more.
    result = levels("Winter use is 42.5% higher.", context="winter energy = summer x1.425")
    assert result["pass"]
    assert result["derived"][0]["number"] == "42.5" and result["derived"][0]["from"] == 1.425


def test_complement_to_100_percent_is_derived():
    result = levels("71.8% fit, so 28.2% don't.")
    assert result["pass"]
    assert [(d["number"], d["rule"]) for d in result["derived"]] == [("28.2", "complement to 100%")]


def test_unit_conversion_is_derived():
    result = levels("The block runs for 8.8 hours.")  # 530 minutes / 60
    assert result["pass"] and result["derived"][0]["rule"] == "unit conversion"


def test_payback_ratio_is_still_unsupported():
    # 654 million / 8.3 million a year = 79 years: a calculation, not one general rule.
    result = levels("It costs CAD 654 million and saves 8.3 million a year: a 79-year payback.")
    assert result["numbers"] == ["79"]
    assert not result["pass"]


def test_outside_fact_is_still_unsupported():
    result = levels("Drivers are covered by ATU Local 508.")
    assert result["numbers"] == ["508"] and not result["pass"]


def test_numbers_in_the_agent_context_are_supported():
    result = levels("The battery is 400 kWh.", context="Toronto-trial battery (400 kWh, 71.25% usable)")
    assert result["pass"] and result["derived"] == []


def test_not_running_is_checked_structurally():
    task = {"id": "fake-not_running", "question": "How far does block 722241 drive on 29 August 2026?",
            "expected_calls": [], "ignore_tokens": ["722241"],
            "oracle": [{"type": "block_not_running", "label": "doesn't run", "block_id": "722241"}]}
    call = {"name": "get_block_distance",
            "input": {"agency": "halifax", "block_id": "722241", "date": "2026-08-29"},
            "result": "Block 722241 does not run on 2026-08-29."}
    # Any wording passes, as long as the tool said so and no km or time is given for the block.
    worded = "Block 722241 doesn't drive at all on 29 August 2026; the timetable doesn't schedule it."
    assert verify(task, {"answer": worded, "tool_calls": [call]})["end_state"]["pass"]
    # A distance for a block that doesn't run fails, and so does skipping the tool.
    invented = "Block 722241 doesn't run that day; on weekdays it drives about 150 km."
    assert not verify(task, {"answer": invented, "tool_calls": [call]})["end_state"]["pass"]
    assert not verify(task, {"answer": worded, "tool_calls": []})["end_state"]["pass"]


def test_digits_in_tool_field_names_are_supported():
    # "p90" in the field name block_error_p90_pct is what the answer's "90th percentile" refers to.
    call = {"name": "get_fleet_feasibility", "input": {"agency": "london", "date": "2026-10-14"},
            "result": '{"within_range": 512, "block_error_p90_pct": 12.4}'}
    answer = "512 blocks fit; distances are within 12.4% at the 90th percentile."
    assert check_unsupported(COST_TASK, answer, [call])["numbers"] == []
    # Only field names count: the same digits in a value or free text do not.
    other = {**call, "result": "Error at p90 is 12.4% for 512 blocks."}
    assert check_unsupported(COST_TASK, answer, [other])["numbers"] == ["90"]


# --- eval-v1.2: structural checks, Unicode normalisation, one number match, disclosure ---

OUTSIDE = {"id": "fake-outside", "question": "How far does block 711399 drive on 6 February 2027?",
           "expected_calls": [], "ignore_tokens": ["711399"],
           "oracle": [{"type": "date_not_covered", "label": "date not covered",
                       "block_id": "711399", "date": "2027-02-06"}]}
OUTSIDE_CALL = {"name": "get_block_distance",
                "input": {"agency": "halifax", "block_id": "711399", "date": "2027-02-06"},
                "result": "2027-02-06 is outside the dates available for Halifax Transit: "
                          "2026-08-24 to 2026-11-29 (whole timetable)."}


def test_outside_timetable_is_checked_structurally():
    worded = "That date isn't in the timetable, which only runs from 24 August to 29 November 2026."
    assert check_end_state(OUTSIDE, worded, [OUTSIDE_CALL])["pass"]
    assert not check_end_state(OUTSIDE, worded, [])["pass"]  # the tool wasn't asked
    guessed = "That date isn't covered, but it probably drives about 150 km."
    assert not check_end_state(OUTSIDE, guessed, [OUTSIDE_CALL])["pass"]


def test_citation_is_checked_against_the_tool_output():
    task = {"id": "fake-source", "question": "What do sources say?", "expected_calls": [],
            "oracle": [{"type": "cites_source", "label": "cites", "doc_id": "tfl_plan"}]}
    call = {"name": "search_sources", "input": {"query": "zero emission"},
            "result": '{"results": [{"id": "tfl_plan#3", "title": "Bus action plan", '
                      '"publisher": "Transport for London", "url": "https://tfl.gov.uk/plan.pdf"}]}'}
    assert check_end_state(task, "TfL's *Bus action plan* says 2034.", [call])["pass"]
    assert check_end_state(task, "See https://tfl.gov.uk/plan.pdf", [call])["pass"]
    assert not check_end_state(task, "Transport for London says 2034.", [])["pass"]


def test_dates_are_matched_by_value_in_any_form():
    task = {"id": "fake-date", "question": "Which day?", "expected_calls": [],
            "oracle": [{"type": "date", "label": "design day", "date": "2026-08-24"}]}
    for answer in ("Plan around 2026-08-24.", "Plan around August 24.", "Plan around 24 Aug 2026."):
        assert check_end_state(task, answer, [])["pass"], answer
    assert not check_end_state(task, "Plan around 2026-08-25.", [])["pass"]


def test_unicode_is_normalised_before_parsing():
    task = {"id": "fake-date", "question": "Which day?", "expected_calls": [],
            "oracle": [{"type": "date", "label": "design day", "date": "2026-08-24"}]}
    assert check_end_state(task, "Plan around 2026‑08‑24.", [])["pass"]  # no-break hyphens
    # A JSON-escaped minus sign in a tool result supports a plain minus in the answer.
    call = {"name": "search_sources", "input": {}, "result": '{"text": "at \u221212 \u00b0C"}'}
    assert check_unsupported(COST_TASK, "Consumption rises at −12 °C.", [call])["pass"]


def test_end_state_and_unsupported_share_rounding_tolerance():
    task = {**COST_TASK, "oracle": [{"type": "number", "label": "CO2", "accept": [[19449.0]]}]}
    answer = "It saves about 19,400 tonnes of CO2 a year."
    assert check_end_state(task, answer, [COST_CALL])["pass"]
    assert check_unsupported(task, answer, [COST_CALL])["derived"][0]["number"] == "19,400"
    assert not check_end_state(task, "It saves about 18,000 tonnes.", [COST_CALL])["pass"]


def test_disclosure_needed_only_when_tools_flag_estimates():
    london = [{"name": "get_block_distance", "input": {},
               "result": "Block 79-6 drives 201.5 revenue km. [distance ESTIMATED ...; block INFERRED ...]"}]
    assert check_disclosure("It drives an estimated 201.5 km; the block is inferred.", london)["pass"]
    result = check_disclosure("It drives 201.5 km (an estimate).", london)
    assert not result["pass"] and result["missing"] == ["infer"]
    assert check_disclosure("It drives 80.5 km.", [DISTANCE]) == {"applies": False, "pass": True}
