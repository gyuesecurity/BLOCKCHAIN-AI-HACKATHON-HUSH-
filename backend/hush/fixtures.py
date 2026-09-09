DEMO_CANDIDATES = [
    {
        "candidate_id": "restaurant-01",
        "name": "모두의 식탁",
        "price": 17000,
        "category": "korean",
        "accessibility_features": ["wheelchair_ramp"],
        "end_time": "20:30",
        "travel_minutes_by_participant": {"A": 20, "B": 25, "C": 15, "D": 25},
    },
    {
        "candidate_id": "restaurant-02",
        "name": "골목 한식당",
        "price": 14000,
        "category": "korean",
        "accessibility_features": [],
        "end_time": "20:30",
        "travel_minutes_by_participant": {"A": 15, "B": 20, "C": 20, "D": 20},
    },
    {
        "candidate_id": "restaurant-03",
        "name": "늦은 정원",
        "price": 15000,
        "category": "korean",
        "accessibility_features": ["wheelchair_ramp"],
        "end_time": "21:30",
        "travel_minutes_by_participant": {"A": 20, "B": 20, "C": 15, "D": 20},
    },
    {
        "candidate_id": "restaurant-04",
        "name": "바다마을",
        "price": 14000,
        "category": "seafood",
        "accessibility_features": ["wheelchair_ramp"],
        "end_time": "20:30",
        "travel_minutes_by_participant": {"A": 20, "B": 20, "C": 15, "D": 20},
    },
]

DEMO_CONSTRAINTS = [
    {
        "constraint_id": "constraint-a-price",
        "participant_pseudonym": "A",
        "constraint_type": "max_price",
        "priority": "HARD",
        "constraint_value": {"amount": 15000, "currency": "KRW"},
    },
    {
        "constraint_id": "constraint-b-food",
        "participant_pseudonym": "B",
        "constraint_type": "excluded_category",
        "priority": "HARD",
        "constraint_value": {"categories": ["seafood"]},
    },
    {
        "constraint_id": "constraint-c-access",
        "participant_pseudonym": "C",
        "constraint_type": "accessibility_required",
        "priority": "HARD",
        "constraint_value": {"features": ["wheelchair_ramp"]},
    },
    {
        "constraint_id": "constraint-d-time",
        "participant_pseudonym": "D",
        "constraint_type": "latest_end_time",
        "priority": "HARD",
        "constraint_value": {"time": "21:00"},
    },
]
