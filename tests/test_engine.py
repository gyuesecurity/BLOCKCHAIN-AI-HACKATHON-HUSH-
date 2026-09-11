from hush.engine import decide
from hush.fixtures import DEMO_CANDIDATES, DEMO_CONSTRAINTS


def _relaxed_to_17000():
    return [
        {**item, "constraint_value": {"amount": 17000, "currency": "KRW"}}
        if item["constraint_id"] == "constraint-a-price"
        else item
        for item in DEMO_CONSTRAINTS
    ]


def test_demo_is_initially_infeasible_and_proposes_minimum_price_relaxation():
    result = decide(DEMO_CANDIDATES, DEMO_CONSTRAINTS)
    assert result.result_type == "INFEASIBLE"
    # B의 음식 조건은 SOFT라 HARD 충돌 집합에 포함되지 않는다.
    assert result.conflicting_constraint_ids == (
        "constraint-a-price",
        "constraint-c-access",
        "constraint-d-time",
    )
    assert result.proposal is not None
    assert result.proposal["participant_pseudonym"] == "A"
    assert result.proposal["proposed_constraint_value"]["amount"] == 17000


def test_accepted_relaxation_produces_deterministic_result():
    changed = _relaxed_to_17000()
    first = decide(DEMO_CANDIDATES, changed)
    second = decide(DEMO_CANDIDATES, changed)
    assert first == second
    assert first.result_type == "FEASIBLE"
    assert first.selected_candidate_id == "restaurant-04"


def test_soft_preference_decides_between_otherwise_equal_candidates():
    changed = _relaxed_to_17000()
    result = decide(DEMO_CANDIDATES, changed)
    # 두 후보 모두 HARD 조건을 통과한다.
    assert set(result.feasible_candidate_ids) == {"restaurant-01", "restaurant-04"}
    # B가 해산물을 선호하지 않으므로 seafood 후보(restaurant-01)가 밀린다.
    assert result.feasible_candidate_ids == ("restaurant-04", "restaurant-01")
    assert result.selected_candidate_id == "restaurant-04"

    # SOFT 선호가 없으면 결정적 tie-break는 candidate_id 순서 → seafood 후보가 선택된다.
    hard_only = [item for item in changed if item["priority"] == "HARD"]
    assert decide(DEMO_CANDIDATES, hard_only).selected_candidate_id == "restaurant-01"


def test_relaxation_below_17000_stays_infeasible():
    for amount in (15000, 16000, 16999):
        changed = [
            {**item, "constraint_value": {"amount": amount, "currency": "KRW"}}
            if item["constraint_id"] == "constraint-a-price"
            else item
            for item in DEMO_CONSTRAINTS
        ]
        assert decide(DEMO_CANDIDATES, changed).result_type == "INFEASIBLE"


def test_minimum_travel_time_relaxation_is_dataset_derived():
    constraints = [
        {
            "constraint_id": "travel-a",
            "participant_pseudonym": "A",
            "constraint_type": "max_travel_minutes",
            "priority": "HARD",
            "constraint_value": {"minutes": 10},
        }
    ]
    result = decide(DEMO_CANDIDATES, constraints)
    assert result.result_type == "INFEASIBLE"
    assert result.proposal["constraint_type"] == "max_travel_minutes"
    assert result.proposal["proposed_constraint_value"] == {"minutes": 15}
    assert result.proposal["relaxation_cost"] == 5


def test_minimum_end_time_relaxation_is_dataset_derived():
    constraints = [
        {
            "constraint_id": "time-a",
            "participant_pseudonym": "A",
            "constraint_type": "latest_end_time",
            "priority": "HARD",
            "constraint_value": {"time": "19:30"},
        }
    ]
    result = decide(DEMO_CANDIDATES, constraints)
    assert result.result_type == "INFEASIBLE"
    assert result.proposal["constraint_type"] == "latest_end_time"
    assert result.proposal["proposed_constraint_value"] == {"time": "20:00"}
    assert result.proposal["relaxation_cost"] == 30


def test_cross_type_relaxation_cost_uses_normalized_units():
    result = decide(DEMO_CANDIDATES, DEMO_CONSTRAINTS)
    assert result.proposal["constraint_type"] == "max_price"
    assert result.proposal["relaxation_cost"] == 2
