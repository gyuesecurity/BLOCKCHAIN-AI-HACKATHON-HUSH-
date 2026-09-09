# Deterministic Decision Engine

Engine은 `constraint_value` normalization, hard evaluation, candidate filtering, feasibility, conflict detection, minimum relaxation search, soft scoring, final selection만 담당한다. UserApproval 생성, ConstraintVersion 변경, Blockchain 호출은 금지된다.

## 입력과 출력

```text
EngineInput = { decision_run_id, frozen_participant_inputs, active_constraint_versions, candidates,
  candidate_dataset_hash, engine_version, engine_code_hash }
EngineOutput = { result_type, input_set_root, feasible_candidate_ids,
  conflict?, relaxation_proposals?, ranked_candidates?, selected_candidate_id? }
```

`active_constraint_versions`는 `frozen_participant_inputs` 중 같은 frozen room roster에 속하고 현재 `ACTIVE`이며 연결된 `Commitment.status`가 `CONFIRMED`인 stale 아닌 `CONSTRAINED` version만 포함한다. Backend는 `DecisionRun` 생성 transaction에서 모든 roster participant의 `frozen_participant_inputs`와 `input_set_leaves`를 freeze한다. `CONSTRAINED` participant는 모든 eligible `HARD`와 `SOFT` version을, `EMPTY` participant는 canonical EMPTY `ParticipantInput` 하나를 제공한다. EMPTY input은 Engine constraint evaluation에는 영향을 주지 않지만 input provenance에는 포함된다. output의 `conflict`에는 internal `conflicting_constraint_version_ids`만 있으며 shared response로 직접 변환하지 않는다.

## Constraint와 Candidate 표현

`ConstraintVersion`은 `{constraint_type,priority,constraint_value}`를 가진다. `max_price`는 `{amount,currency}`, `excluded_category`는 `{categories:[string]}`, `accessibility_required`는 `{features:[string]}`, `max_travel_minutes`는 `{minutes}`, `latest_end_time`은 `{time:"HH:MM"}`다. `Candidate`는 `candidate_id`, `price`, `category`, `accessibility_features`, `travel_minutes_by_participant`, `end_time`을 가진다. 통화와 time zone은 room dataset에서 하나로 고정하며 다른 값은 validation failure다.

## Hard와 Soft 규칙

`HARD`는 `00-scope.md`의 table 규칙으로 boolean 평가하며 하나라도 false면 탈락한다. `SOFT`는 동일 type의 만족 여부를 weight로 합산한다. weight는 canonical input에 포함된 정수이며 P0 default는 1이다. `SOFT` 위반은 feasibility나 relaxation 대상이 아니다.

## Conflict와 Minimum Relaxation

candidate가 0개면 Engine은 inclusion-minimal conflict set을 deterministic하게 찾는다. 동일 크기의 set이 여러 개면 정렬된 `constraint_version_id` lexicographic 순서로 하나를 선택한다. 이 결과는 Backend의 private routing에만 사용한다.

완화 탐색은 지원 type의 `HARD` version 하나씩에 대해 dataset 값으로 만들 수 있는 가장 작은 loosened bound를 계산한다. 각 proposal은 원 bound보다 엄격해질 수 없고, 대상이 아닌 constraint를 변경하지 않는다. 순위는 다음 tuple의 오름차순이다.

`(changed_constraint_count, relaxation_cost, disclosure_cost, -feasible_candidate_count, constraint_version_id)`

P0에서 `changed_constraint_count`는 항상 1이고 `disclosure_cost`는 공개량이 아니라 private delivery 비용으로 0이다. 따라서 private raw data 공개를 계산상 허용하지 않는다. 가장 높은 proposal만 해당 owner에게 보내며, proposal 계산은 실제 변경이 아니다.

## 최종 선택과 결정성

feasible candidate는 soft score 내림차순, `candidate_id` 오름차순으로 선택한다. 부동소수점은 금지하고 amount/minutes/score는 integer로 처리한다. 입력 배열은 `constraint_version_id`, `candidate_id`로 정렬하고 canonical JSON으로 serialize한다. 동일한 `EngineInput`과 `engine_version`/`engine_code_hash`는 byte-equivalent output을 만들어야 한다.

## Pseudocode

```text
normalize_and_validate(input)
leaves = sort(input_set_leaf(frozen_participant_inputs) by byte order)
input_set_root = keccak256(canonical_json(leaves))
feasible = [c for c in candidates if every HARD constraint evaluates true]
if feasible is empty:
  conflict = deterministic_minimal_conflict(active HARD constraints)
  proposals = rank(single_constraint_relaxations(conflict, candidates))
  return INFEASIBLE, conflict, top private proposal(s)
ranked = sort(feasible by (-soft_score(c), candidate_id))
return FEASIBLE, ranked, ranked[0]
```

## Engine identity와 실패

`engine_version`과 `engine_code_hash`는 build 전에 고정되어 모든 `DecisionRun`, `FinalDecision`, `decision_commitment`에 포함된다. 지원하지 않는 type/value, duplicate active version, roster mismatch, unconfirmed/stale version, dataset hash mismatch, overflow, 비결정적 dependency, 계산 timeout은 `FAILED`다. 실패한 run은 final selection을 만들지 않으며 Backend는 계산 결과를 추측하거나 대체하지 않는다.
