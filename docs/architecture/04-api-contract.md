# P0 REST API 계약

모든 private endpoint는 PD-001의 `participant_id`에 바인딩된 opaque participant session을 요구한다. `Idempotency-Key` header는 state를 만드는 `POST`에 required다. error body는 `{ "code": "...", "message": "한국어 사용자 메시지", "request_id": "..." }`이며 private detail을 포함하지 않는다.

## 공통 규칙

`GET /rooms/{decision_room_id}`는 Shared Room용 safe projection만 반환한다: `status`, `required_participant_count`, `participant_count`, `input_confirmed_participant_count`, `eligible_participant_count`, generic `decision_status`. private endpoint는 owner object만 반환한다. `409 STALE_CONSTRAINT_VERSION`, `409 INVALID_STATE`, `403 FORBIDDEN`, `404 NOT_FOUND`, `422 VALIDATION_ERROR`, `429 RATE_LIMITED`, `503 DEPENDENCY_UNAVAILABLE`를 공통 사용한다.

## Room과 Participant

| Method / Path | Purpose·Allowed State | Request → Response | Side Effect·Privacy |
|---|---|---|---|
| `POST /rooms` | room 생성 / `DRAFT` | `{title,required_participant_count,candidate_dataset_version}` → `{decision_room_id,status,required_participant_count,candidate_dataset_hash}` | `OPEN`으로 전환; creator session만 반환 |
| `POST /rooms/{decision_room_id}/participants` | 초대 participant 참여 / `OPEN`,`COLLECTING` | `{invite_token}` → `{participant_id,participant_pseudonym,status,input_status}` | `JOINED`; required roster가 찬 뒤 join 불가; 자신의 ID만 반환 |
| `GET /rooms/{decision_room_id}` | shared 진행 조회 / 비terminal | 없음 → safe projection | participant별 field 없음 |
| `GET /rooms/{decision_room_id}/participants/me` | 내 상태 조회 | 없음 → 내 `Participant` | 자신의 status만 반환 |

## 비공개 입력, AI, Constraint

| Method / Path | Purpose·Allowed State | Request → Response | State Transition·Idempotency·Privacy |
|---|---|---|---|
| `POST /rooms/{decision_room_id}/private-inputs` | 자연어 입력 / `COLLECTING` | `{source_text}` → `{private_input_id,status}` | `RECEIVED`; raw text는 owner private, idempotent |
| `POST /rooms/{decision_room_id}/private-inputs/{private_input_id}/parse` | AI parsing / `COLLECTING` | `{}` → `{parse_id,status,structured_candidates}` | AI output은 candidate일 뿐; private, 재시도는 같은 parse ID |
| `GET /rooms/{decision_room_id}/constraints/drafts` | 내 AI candidate 조회 | 없음 → `{constraints:[{constraint_type,priority,constraint_value,explanation}]}` | 타인 draft 제외 |
| `POST /rooms/{decision_room_id}/constraints` | 사용자 확정 / `COLLECTING` | `{constraint_type,priority,constraint_value,source_text?}` → `{constraint_id,constraint_version_id,constraint_version:1,status,condition_commitment,commitment_status}` | user confirmation 뒤 `PENDING_ACTIVATION`과 `PENDING` 게시 시도를 생성, idempotent |
| `GET /rooms/{decision_room_id}/constraints/me` | 내 version 조회 | 없음 → `{constraints:[...]}` | source text/value/proposal은 owner만 |
| `POST /rooms/{decision_room_id}/input-confirmations` | 이번 room input 제출 완료 선언 / `COLLECTING` | `{input_mode:"CONSTRAINED"|"EMPTY"}` → `{input_status:"INPUT_CONFIRMED",input_mode}` | `CONSTRAINED`는 eligible version 하나 이상, `EMPTY`는 condition 없이 salted canonical EMPTY `ParticipantInput`을 생성하는 것이 전제; 새 논리적 Constraint 추가는 confirmation을 다시 요구하나, 기존 Constraint에 대한 accepted relaxation은 이미 `UserApproval`을 가지므로 다시 요구하지 않음 |

확정 요청의 예시는 다음과 같다.

```json
{"constraint_type":"max_price","priority":"HARD","constraint_value":{"amount":15000,"currency":"KRW"},"source_text":"2만원 넘는 곳은 부담스러워"}
```

## Decision과 Conflict

| Method / Path | Purpose·Allowed State | Response | Side Effect·Privacy |
|---|---|---|---|
| `POST /rooms/{decision_room_id}/decision-runs` | 실행 / `READY` | `{decision_run_id,status:"QUEUED",input_set_root}` | required roster와 모든 frozen `participant_inputs`를 atomic snapshot으로 freeze; `CONSTRAINED`는 모든 eligible version, `EMPTY`는 canonical EMPTY input 하나를 포함, idempotent |
| `GET /rooms/{decision_room_id}/decision-runs/{decision_run_id}` | shared 결과 조회 | `{status,result_type,feasible_candidate_count?,decision_status}` | `INFEASIBLE`이면 generic status만; conflict owner/value 없음 |
| `GET /rooms/{decision_room_id}/relaxation-proposals/me` | 내 proposal 조회 / `NEGOTIATING` | `{proposals:[{relaxation_proposal_id,constraint_version_id,current_constraint_value,proposed_constraint_value,feasible_candidate_count,status,expires_at}]}` | 대상 owner만 상세 반환 |

`DecisionRun` 성공 예시: `{ "status":"FEASIBLE", "result_type":"FEASIBLE", "feasible_candidate_count":3, "decision_status":"FINALIZING" }`. infeasible shared 예시: `{ "status":"INFEASIBLE", "result_type":"INFEASIBLE", "decision_status":"PRIVATE_ADJUSTMENT_AVAILABLE" }`.

## Relaxation 승인

| Method / Path | Purpose·Allowed State | Request → Response | Transition·오류 |
|---|---|---|---|
| `POST /rooms/{decision_room_id}/relaxation-proposals/{relaxation_proposal_id}/accept` | 제안 승인 / `PROPOSED` | `{constraint_version_id}` → `{user_approval_id,decision:"ACCEPTED",new_constraint_version_id,constraint_version,condition_commitment,commitment_status}` | new version=`PENDING_ACTIVATION`, new commitment=`PENDING`; old `ACTIVE`는 confirmation 전 유지; owner/version 불일치는 `403`/`409` |
| `POST /rooms/{decision_room_id}/relaxation-proposals/{relaxation_proposal_id}/reject` | 제안 거부 / `PROPOSED` | `{constraint_version_id}` → `{user_approval_id,decision:"REJECTED",status:"REJECTED"}` | 원 version 유지; duplicate는 같은 결과 반환 |

Backend는 accept 요청이 proposal의 `constraint_version_id`와 현재 `ACTIVE`+`CONFIRMED` version에 동시에 일치할 때만 처리한다. new commitment를 포함한 single `supersedeCondition`의 successful mined receipt 후 compare-and-set/database transaction으로만 old `ACTIVE → SUPERSEDED`, new `PENDING_ACTIVATION → ACTIVE`, `Commitment PENDING → CONFIRMED`를 원자 적용한다. AI, Engine, Smart Contract에는 이 endpoint를 호출할 권한이 없다.

## Final Decision, Receipt, Verification data

| Method / Path | Purpose·Allowed State | Response·Privacy |
|---|---|---|
| `GET /rooms/{decision_room_id}/final-decision` | shared final 조회 / `COMPLETED` | `{final_decision_id,candidate_id,candidate_name,decision_commitment,status}`; 다른 private input 없음 |
| `GET /rooms/{decision_room_id}/receipts/me` | 내 receipt 조회 / `COMPLETED` | `ParticipantReceipt`의 `participant_inputs` 배열과 공통 provenance; owner만 |
| `GET /rooms/{decision_room_id}/verification-data/me` | 독립 검증 입력 조회 | `{decision_run_id,participant_inputs,input_set_leaves,input_set_root,candidate_dataset_hash,engine_version,engine_code_hash,final_decision_hash,decision_commitment,transaction_hash,network,contract_address}`; owner만 |

각 `participant_inputs` entry는 `{participant_input_id,input_mode,constraint_id?,constraint_version_id?,constraint_version?,condition_commitment,input_set_leaf}`다. `CONSTRAINED` entry는 constraint field를 모두 포함하고 `EMPTY` entry는 constraint field 없이 canonical EMPTY `condition_commitment`와 leaf를 포함한다. `verification-data`는 raw `constraint_value`나 salt를 반환하지 않는다. `input_set_leaves`는 P0 root 재계산을 위한 제한적 metadata disclosure이며 다른 participant identity 또는 leaf의 직접 mapping을 포함하지 않는다. participant가 각 leaf의 preimage 재계산을 원하면 별도의 로컬 receipt export에서만 자기 raw value와 salt를 사용하며 API logging 대상이 아니다.

## 재시도와 authorization

동일 `Idempotency-Key`와 같은 body는 최초 성공 응답을 재현한다. 다른 body로 재사용하면 `409 IDEMPOTENCY_KEY_REUSED`다. transaction pending은 `202`와 `commitment_status:"PENDING"`으로 응답하며 processing은 final commitment 단계에서만 대기한다. `GET`은 idempotent이고, authorization 실패는 object 존재 여부를 누설하지 않도록 `404`를 사용할 수 있다.
