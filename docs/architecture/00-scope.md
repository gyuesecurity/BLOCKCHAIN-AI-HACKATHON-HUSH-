# P0 범위

## 프로젝트 목표와 P0 목표

HUSH는 참가자가 raw private condition이나 개인 사유를 다른 참가자에게 공개하지 않고 집단 결정을 만들며, 승인한 조건 버전이 최종 결정에 반영되었음을 독립적으로 검증하게 한다. P0 Goal은 4인 식당 데모에서 canonical lifecycle 전체를 반복 가능하게 보이는 것이다.

## 포함 범위

- 비공개 자연어 입력, AI structured candidate, 명시적 사용자 확정, off-chain 보관
- deterministic hard filtering, soft scoring, feasibility, conflict detection, minimum relaxation proposal
- 대상 participant에게만 전달하는 proposal, accept/reject, 승인 뒤 supersession과 re-commit
- immutable EVM testnet Decision Registry, Participant Receipt, explorer/manual verification
- Participant UI, Shared Room UI, Verification UI

## 지원하는 Constraint Types

| `constraint_type` | candidate field | Hard rule | P0 relaxation |
|---|---|---|---|
| `max_price` | `price` | `price <= constraint_value.amount` | amount 상향 |
| `excluded_category` | `category` | `category`가 `categories`에 없음 | 없음 |
| `accessibility_required` | `accessibility_features` | 요구 feature가 모두 존재 | 없음 |
| `max_travel_minutes` | `travel_minutes_by_participant` | participant별 시간이 값 이하 | minutes 상향 |
| `latest_end_time` | `end_time` | 종료 시각이 값 이하 | 시각을 뒤로 이동 |

각 Constraint는 `HARD` 또는 `SOFT`다. P0의 `SOFT`는 위 type을 선호로 재사용할 수 있으나 candidate를 탈락시키지 않는다. 표에 없는 자연어는 canonical Constraint가 될 수 없다.

## 지원하는 Relaxation Types

`max_price`, `max_travel_minutes`, `latest_end_time`만 `RelaxationProposal`을 만들 수 있다. proposal은 한 `ConstraintVersion`만 느슨하게 만들 수 있다. `excluded_category`와 `accessibility_required`는 P0에서 완화하지 않는다.

## 제외 범위와 비목표

P0는 Engine 계산 정확성을 암호학적으로 증명하지 않으며, 타인의 raw condition·사유·salt·conflict ownership을 공개하지 않는다. 완전 익명성, 범용 자연어 제약, 운영자 없는 governance, MPC, production enterprise connector도 목표가 아니다. Blockchain은 AI나 Engine의 정답을 보증하지 않는다.

## P1과 P2

P1: 가격 상한 ZK Proof, Merkle `input_set_root`, participant 서명 강화, 협상안 비교 UI. P2: DAO/decentralized governance, MPC, Local/On-device LLM, 모든 Constraint ZK, 복잡한 Smart Contract governance, 기업 연동, 완전 익명성 protocol. 모두 Future Extension이다.

## 데모 시나리오

QR로 참여한 4명이 가격·음식·접근성·시간/이동 조건을 확정하고 `commitCondition`으로 기록한다. 첫 `DecisionRun`은 infeasible이며 Shared Room에는 identity 없이 한 건의 private adjustment만 필요하다고 보인다. 해당 participant만 수치형 proposal을 accept 또는 reject한다. accept면 `constraint_version` 2와 new commitment를 포함한 single `supersedeCondition`이 기록되고, 최종 식당 결정과 receipt를 각자가 검증한다.

## 완료 정의

4개의 확정 commitment, 비귀속 conflict, accept와 reject 경로, stale/superseded version 차단, `input_set_root`·`candidate_dataset_hash`·Engine identity에 연결된 final decision, on-chain record와 일치하는 receipt를 재현한다. `09-security-and-privacy.md`의 privacy·user control·verification 점검도 통과해야 한다.

## IMPLEMENTATION DECISION

**ID-001 — Canonical serialization:** RFC 8785 호환 canonical JSON을 hashing 전에 사용한다. 구현 언어의 key ordering 차이 없이 재현하기 위해서다.

**ID-002 — Candidate dataset:** room 생성 시 versioned off-chain dataset과 `candidate_dataset_hash`를 고정한다. 외부 데이터 공급자 의존 없이 P0 계산을 재현하기 위한 선택이다.
