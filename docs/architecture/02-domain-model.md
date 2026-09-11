# 정본 Domain Model

모든 객체는 아래 이름과 field를 다른 문서에서도 그대로 사용한다. private field의 visibility는 owner와 authorized Backend/Engine에 한정된다.

## 객체 정의

| Object | Purpose / Identifier | 핵심 fields | Owner·Visibility·Persistence |
|---|---|---|---|
| `DecisionRoom` | 집단 결정 단위 / `decision_room_id` | `title`, `status`, `required_participant_count`, `candidate_dataset_hash`, `candidate_dataset_version`, `created_at` | room creator가 관리, aggregate만 shared, off-chain |
| `Participant` | room의 참여자 / `participant_id` | `decision_room_id`, `participant_pseudonym`, `status`, `input_status`, `input_mode`, `joined_at` | 본인과 Backend, pseudonym만 public, off-chain |
| `Constraint` | participant 소유의 논리적 조건 / `constraint_id` | `participant_id`, `decision_room_id`, `constraint_type`, `priority`, `visibility` | 본인 private, off-chain; version들의 부모 |
| `ConstraintVersion` | 확정된 조건의 불변 snapshot / `constraint_version_id` | `constraint_id`, `participant_input_id`, `constraint_version`, `constraint_value`, `source_text`, `status`, `condition_commitment`, `supersedes_constraint_version_id` | 본인 private; commitment와 version만 public |
| `Commitment` | 하나의 on-chain 게시 시도 / `commitment_id` | `constraint_version_id`, `condition_commitment`, `attempt`, `replaces_commitment_id`, `transaction_hash`, `block_number`, `status` | Backend가 게시, public hash/provenance, off-chain tracking |
| `ParticipantInput` | DecisionRun에 freeze할 participant별 canonical input 표현 / `participant_input_id` | `decision_room_id`, `participant_id`, `input_mode`, `constraint_id?`, `constraint_version_id?`, `constraint_version?`, `condition_commitment` | participant와 Backend private; receipt에는 owner의 entry만 직접 식별 |
| `Candidate` | 고정 dataset의 선택지 / `candidate_id` | `name`, `price`, `category`, `accessibility_features`, `end_time`, `travel_minutes_by_participant` | room dataset, raw dataset는 off-chain; hash는 public provenance |
| `DecisionRun` | Engine 실행 record / `decision_run_id` | `decision_room_id`, `input_roster`, `frozen_participant_inputs`, `frozen_constraint_version_ids`, `input_set_leaves`, `input_set_root`, `candidate_dataset_hash`, `engine_version`, `engine_code_hash`, `status`, `result_type` | Backend가 orchestration, conflict detail은 private, off-chain |
| `Conflict` | infeasibility의 내부 분석 / `conflict_id` | `decision_run_id`, `conflicting_constraint_version_ids`, `status` | Engine/Backend private, participant별 detail은 해당 owner만 |
| `RelaxationProposal` | 한 version을 느슨하게 하는 제안 / `relaxation_proposal_id` | `constraint_version_id`, `proposed_constraint_value`, `relaxation_cost`, `feasible_candidate_count`, `status`, `expires_at` | 대상 participant만 private, off-chain |
| `UserApproval` | 명시적 accept/reject 증적 / `user_approval_id` | `relaxation_proposal_id`, `participant_id`, `decision`, `approved_at`, `idempotency_key` | 해당 participant와 Backend, off-chain audit |
| `FinalDecision` | 최종 선택과 provenance / `final_decision_id` | `decision_run_id`, `candidate_id`, `input_set_root`, `candidate_dataset_hash`, `engine_version`, `engine_code_hash`, `final_decision_hash`, `decision_commitment`, `status` | candidate와 public hashes shared; off-chain+on-chain provenance |
| `ParticipantReceipt` | 개인 검증 package / `participant_receipt_id` | `participant_id`, `decision_run_id`, `final_decision_id`, `participant_inputs`, `input_set_leaves`, `input_set_root`, `candidate_dataset_hash`, `engine_version`, `engine_code_hash`, `final_decision_hash`, `decision_commitment`, `transaction_hash`, `network`, `contract_address` | 본인만 private retrieval; public record와 대조 가능 |

## field 계약과 관계

`Constraint.priority`는 `HARD` 또는 `SOFT`, `Constraint.visibility`는 P0에서 항상 `PRIVATE`다. `constraint_value`는 type별 schema를 따르며 `source_text`와 private reason은 on-chain 또는 shared response에 절대 포함되지 않는다. `Participant.input_status`는 `PENDING_INPUT` 또는 `INPUT_CONFIRMED`이며, 후자는 participant가 이번 room의 canonical input 제출을 끝냈음을 뜻한다. `Participant.input_mode`는 `CONSTRAINED` 또는 `EMPTY`다. `EMPTY`는 condition 없이도 제출 완료를 명시하는 canonical input이다. 이 두 field는 `ConstraintVersion` 또는 `Commitment` 상태가 아니다.

`ParticipantInput.input_mode=CONSTRAINED`이면 `constraint_id`, `constraint_version_id`, `constraint_version`, `condition_commitment`가 required이며 `participant_input_id`는 해당 `ConstraintVersion`과 1:1이다. `input_mode=EMPTY`이면 constraint field는 absent이고, `condition_commitment`는 canonical empty payload의 salted commitment다. EMPTY payload는 `{decision_room_id,participant_pseudonym,participant_input_id,input_mode:"EMPTY",empty_marker:"HUSH_P0_EMPTY",salt}`로 canonical serialize한다. 따라서 다른 participant·room·empty submission은 같은 commitment가 될 수 없다.

`DecisionRoom` 1개는 여러 `Participant`, `Constraint`, `ParticipantInput`, `DecisionRun`을 가진다. `Participant` 1명은 zero or more `Constraint`와 하나의 현재 canonical input declaration을 가진다. `Constraint` 1개는 one or more `ConstraintVersion`을 가지며 한 시점에 `ACTIVE`는 최대 하나다. `ParticipantInput`은 `CONSTRAINED` ConstraintVersion과 1:1이거나 `EMPTY` declaration과 1:1이다. `DecisionRun`은 frozen roster와 one or more frozen `ParticipantInput`을 가진다. `ParticipantReceipt`은 한 participant의 frozen `participant_inputs` 배열을 가진다. 최초 commitment confirmation 전에는 `ACTIVE`가 없을 수 있다. `ConstraintVersion`은 `PENDING_ACTIVATION`, `ACTIVE`, `SUPERSEDED`, `RETIRED`만 사용한다. `Commitment.status`는 별도 lifecycle인 `PENDING`, `CONFIRMED`, `FAILED`만 사용한다.

Decision eligibility는 해당 room/participant 소유, 현재 `ACTIVE`, stale 아님, 그리고 연결된 `Commitment.status`가 `CONFIRMED`인 version을 모두 만족하는 경우다. `DecisionRoom`은 `required_participant_count`와 같은 수의 non-`REVOKED` participant를 roster로 사용한다. 각 roster participant는 `INPUT_CONFIRMED`여야 하고, `input_mode=CONSTRAINED`이면 하나 이상의 eligible version, `input_mode=EMPTY`이면 condition 없는 명시적 빈 canonical input을 가져야 한다. 따라서 Hard Constraint를 하나 이상 강제하지 않는다.

## lifecycle과 저장 규칙

`ConstraintVersion`은 수정하지 않는다. 최초 확정은 새 version을 `PENDING_ACTIVATION`과 `Commitment.status=PENDING`으로 만들고 `commitCondition`을 제출한다. successful receipt 후 해당 version을 `ACTIVE`, Commitment를 `CONFIRMED`로 전환한다. relaxation accept는 successor version을 `PENDING_ACTIVATION`과 `PENDING`으로 만들고 **new commitment를 포함한 단일 `supersedeCondition`**을 제출한다. successful receipt 뒤에만 원자적으로 predecessor `ACTIVE → SUPERSEDED`, successor `PENDING_ACTIVATION → ACTIVE`, successor Commitment `PENDING → CONFIRMED`로 전환한다. 실패하면 predecessor `ACTIVE`+`CONFIRMED`는 유지되고 successor는 `PENDING_ACTIVATION`, Commitment는 `FAILED`다. 재게시가 필요하면 실패 record를 보존하고 같은 `condition_commitment`의 새 `Commitment.attempt`를 만든다.

`DecisionRun`은 시작 시 roster의 모든 canonical input을 `frozen_participant_inputs`로 snapshot한다. `CONSTRAINED` participant는 모든 eligible `ACTIVE`+`CONFIRMED` ConstraintVersion을, `EMPTY` participant는 하나의 canonical EMPTY `ParticipantInput`을 제공한다. 따라서 `HARD`와 `SOFT` 모두 input set에 들어가며 superseded/unconfirmed/stale version과 run 시작 후 생성된 version은 제외된다. 모든 frozen roster participant는 최소 하나의 input representation을 가진다. run 시작 뒤 join/leave 또는 새 version이 생겨도 이 frozen input은 바뀌지 않으며 다음 run에만 반영된다. raw private fields와 salt는 encrypted off-chain storage에, public verification field는 immutable contract event와 receipt에 저장한다.

## 필수 / 선택 field

모든 ID, owner 관계, status를 가진 객체의 `status`, 생성 timestamp는 required다. `source_text`는 AI parsing을 사용한 경우 required지만 직접 구조화 입력이면 optional이다. `ConstraintVersion.condition_commitment`와 tx fields는 lifecycle의 해당 단계 전 optional이며 완료 후 required다. `ParticipantInput.condition_commitment`는 `CONSTRAINED`와 `EMPTY` 모두 required다. `supersedes_constraint_version_id`와 `final_decision_id`는 해당 lifecycle 전 optional이다. `Conflict`와 `RelaxationProposal`은 infeasible run에서만 존재한다.
