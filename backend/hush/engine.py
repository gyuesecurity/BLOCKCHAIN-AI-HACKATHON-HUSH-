from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import ceil
from typing import Any


@dataclass(frozen=True)
class EngineResult:
    result_type: str
    feasible_candidate_ids: tuple[str, ...]
    selected_candidate_id: str | None = None
    conflicting_constraint_ids: tuple[str, ...] = ()
    proposal: dict[str, Any] | None = None


def _hard_satisfied(candidate: dict[str, Any], constraint: dict[str, Any]) -> bool:
    value = constraint["constraint_value"]
    kind = constraint["constraint_type"]
    if kind == "max_price":
        return candidate["price"] <= value["amount"]
    if kind == "excluded_category":
        return candidate["category"] not in value["categories"]
    if kind == "accessibility_required":
        return set(value["features"]).issubset(candidate["accessibility_features"])
    if kind == "max_travel_minutes":
        owner = constraint["participant_pseudonym"]
        return candidate["travel_minutes_by_participant"][owner] <= value["minutes"]
    if kind == "latest_end_time":
        return candidate["end_time"] <= value["time"]
    raise ValueError(f"unsupported constraint type: {kind}")


def _soft_score(candidate: dict[str, Any], constraints: list[dict[str, Any]]) -> int:
    return sum(
        int(item.get("weight", 1))
        for item in constraints
        if item["priority"] == "SOFT" and _hard_satisfied(candidate, item)
    )


def _feasible(
    candidates: list[dict[str, Any]], constraints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    hard = [item for item in constraints if item["priority"] == "HARD"]
    return [
        candidate
        for candidate in candidates
        if all(_hard_satisfied(candidate, item) for item in hard)
    ]


def _time_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _relaxation_candidates(
    target: dict[str, Any], candidates: list[dict[str, Any]]
) -> list[tuple[int, dict[str, Any]]]:
    """Return deterministic, strictly looser dataset-derived bounds.

    P0 deliberately supports one changed HARD constraint per proposal.  Bounds
    come from the frozen candidate dataset so the search is finite and
    reproducible across machines.
    """

    kind = target["constraint_type"]
    value = target["constraint_value"]
    owner = target["participant_pseudonym"]
    if kind == "max_price":
        current = value["amount"]
        return [
            # P0 relaxation cost is a unitless integer score: KRW is measured
            # in 1,000-won steps while travel/end-time use one-minute steps.
            # Comparing raw KRW with minutes would make ranking meaningless.
            (ceil((bound - current) / 1000), {"amount": bound, "currency": value["currency"]})
            for bound in sorted({item["price"] for item in candidates if item["price"] > current})
        ]
    if kind == "max_travel_minutes":
        current = value["minutes"]
        return [
            (bound - current, {"minutes": bound})
            for bound in sorted(
                {
                    item["travel_minutes_by_participant"][owner]
                    for item in candidates
                    if item["travel_minutes_by_participant"][owner] > current
                }
            )
        ]
    if kind == "latest_end_time":
        current = _time_minutes(value["time"])
        bounds = sorted(
            {
                (_time_minutes(item["end_time"]), item["end_time"])
                for item in candidates
                if _time_minutes(item["end_time"]) > current
            }
        )
        return [(minutes - current, {"time": text}) for minutes, text in bounds]
    return []


def _minimum_numeric_relaxation(
    candidates: list[dict[str, Any]], constraints: list[dict[str, Any]]
) -> dict[str, Any] | None:
    proposals: list[tuple[int, int, str, dict[str, Any]]] = []
    for target in constraints:
        if target["priority"] != "HARD":
            continue
        for cost, proposed_value in _relaxation_candidates(target, candidates):
            changed = [
                {**item, "constraint_value": proposed_value}
                if item["constraint_id"] == target["constraint_id"]
                else item
                for item in constraints
            ]
            feasible = _feasible(candidates, changed)
            if feasible:
                proposal = {
                    "constraint_id": target["constraint_id"],
                    "participant_pseudonym": target["participant_pseudonym"],
                    "constraint_type": target["constraint_type"],
                    "current_constraint_value": target["constraint_value"],
                    "proposed_constraint_value": proposed_value,
                    "relaxation_cost": cost,
                    "feasible_candidate_count": len(feasible),
                }
                proposals.append((cost, -len(feasible), target["constraint_id"], proposal))
                break
    return min(proposals, default=(0, 0, "", None))[-1]


def _minimal_conflict(constraints: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> tuple[str, ...]:
    hard = sorted(
        (item for item in constraints if item["priority"] == "HARD"),
        key=lambda item: item["constraint_id"],
    )
    for size in range(1, len(hard) + 1):
        for subset in combinations(hard, size):
            if not _feasible(candidates, list(subset)):
                return tuple(item["constraint_id"] for item in subset)
    return ()


def decide(candidates: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> EngineResult:
    feasible = _feasible(candidates, constraints)
    if not feasible:
        return EngineResult(
            result_type="INFEASIBLE",
            feasible_candidate_ids=(),
            conflicting_constraint_ids=_minimal_conflict(constraints, candidates),
            proposal=_minimum_numeric_relaxation(candidates, constraints),
        )
    ranked = sorted(
        feasible,
        key=lambda candidate: (
            -_soft_score(candidate, constraints),
            candidate["candidate_id"],
        ),
    )
    return EngineResult(
        result_type="FEASIBLE",
        feasible_candidate_ids=tuple(item["candidate_id"] for item in ranked),
        selected_candidate_id=ranked[0]["candidate_id"],
    )
