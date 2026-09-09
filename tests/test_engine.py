from hush.engine import decide
from hush.fixtures import DEMO_CANDIDATES, DEMO_CONSTRAINTS


def test_demo_is_initially_infeasible_and_proposes_minimum_price_relaxation():
    result = decide(DEMO_CANDIDATES, DEMO_CONSTRAINTS)
    assert result.result_type == "INFEASIBLE"
    assert result.conflicting_constraint_ids == (
        "constraint-a-price",
        "constraint-b-food",
        "constraint-c-access",
        "constraint-d-time",
    )
    assert result.proposal is not None
    assert result.proposal["participant_pseudonym"] == "A"
    assert result.proposal["proposed_constraint_value"]["amount"] == 17000


def test_accepted_relaxation_produces_deterministic_result():
    changed = [
        {**item, "constraint_value": {"amount": 17000, "currency": "KRW"}}
        if item["constraint_id"] == "constraint-a-price"
        else item
        for item in DEMO_CONSTRAINTS
    ]
    first = decide(DEMO_CANDIDATES, changed)
    second = decide(DEMO_CANDIDATES, changed)
    assert first == second
    assert first.result_type == "FEASIBLE"
    assert first.selected_candidate_id == "restaurant-01"
