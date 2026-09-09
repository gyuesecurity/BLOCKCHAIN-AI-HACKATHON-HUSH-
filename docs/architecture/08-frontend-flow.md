# Frontend 흐름

Frontend는 Participant UI, Shared Room UI, Verification UI를 분리한다. 한 화면의 편의가 private data disclosure를 정당화하지 않는다.

## Participant UI

| 화면 / Purpose | Visible Data | Hidden Data | Allowed Action·API | Loading·Error·Privacy |
|---|---|---|---|---|
| Decision Room 참여 | room title, 내 join status | 타인의 ID/condition | 참여 / `POST /participants` | invite 오류는 room 존재를 누설하지 않음 |
| Private Input | 내 `source_text` draft | 다른 participant 전부 | 제출·parse / `POST /private-inputs`, `/parse` | AI 대기, 직접 구조화 입력 fallback; 외부 LLM 고지 |
| AI Interpretation | 내 structured candidate, explanation | AI confidence 이외 타인 data | 수정·확정 / `POST /constraints` | validation 오류는 field별 표시; 자동 확정 금지 |
| Commitment | 내 version, `condition_commitment`, `ConstraintVersion.status`, `Commitment.status` | salt, 타인의 commitment detail | 상태 조회 / `GET /constraints/me` | `PENDING_ACTIVATION`/`ACTIVE`와 `PENDING`/`CONFIRMED`/`FAILED`를 구분; 기존 active condition은 replacement confirmation 전 유지 |
| Private Negotiation | 내 원값·proposal 값·feasible count | conflict owner, 타인 type/value | accept/reject / proposal endpoint | 만료·stale를 명시; 선택 전 원 condition 유지 |
| Participant Receipt | 내 receipt와 explorer link | 타인의 leaf preimage/raw data | receipt·verification 조회 | explorer 장애 시 raw tx/hash 복사 제공 |

## Shared Room UI

Purpose는 합의 진행을 공유하는 것이지 private negotiation을 공개하는 것이 아니다. visible data는 `participant_count`, `committed_participant_count`, generic `decision_status`, final candidate, aggregate `HARD CONSTRAINTS 4/4`, user-approved relaxation count뿐이다. hidden data는 participant identity와 condition의 연결, `constraint_type`, `constraint_value`, source text, private reason, conflict set, proposal 대상 및 내용이다.

허용 action은 room refresh와 authorized decision 시작(`POST /decision-runs`)이다. loading에는 “계산 중”, error에는 generic retry 안내만 보인다. `INFEASIBLE`은 “Private conflict detected. Raw private conditions shared: NO”와 같은 generic 문구로, `NEGOTIATING`은 “A minimal private adjustment is available”로 표시한다. participant 수가 작아도 owner를 추측하게 하는 상세 count/type을 추가하지 않는다.

## Verification UI

Purpose는 HUSH 표시를 믿게 하는 것이 아니라 receipt와 public record를 participant가 비교하게 하는 것이다. visible data는 `decision_run_id`, 자신의 `participant_inputs[]` entry별 `participant_input_id`, `input_mode`, constraint 식별 field(있는 경우), `condition_commitment`, `input_set_leaf`, 그리고 `input_set_leaves`, `input_set_root`, `candidate_dataset_hash`, `engine_version`, `engine_code_hash`, `final_decision_hash`, `decision_commitment`, `transaction_hash`, `network`, `contract_address`다. `EMPTY` entry도 같은 배열에서 표시한다. raw condition과 salt는 기본 UI에 표시하지 않는다. `input_set_leaves`는 P0 root 재계산에 필요한 제한적 metadata이며 다른 participant identity와 leaf의 mapping을 표시하지 않는다.

`GET /verification-data/me`로 evidence를 받고 각 `participant_inputs`의 leaf를 확인한다. 모든 내 leaf가 `input_set_leaves`에 있는지 확인한 뒤 전체 leaf set을 정렬·canonical serialize하여 root를 재계산하고 explorer/RPC public read로 event를 대조한다. local recomputation은 user device에서만 수행한다. `PENDING`, `VERIFIED`, `INVALID`, `EXPLORER_UNAVAILABLE`을 구별하고 `VERIFIED`는 mined public record 일치 후에만 보인다.

## 정본 데모 흐름

`Decision Room → Private Input → AI Interpretation → User Confirmation → Commitment → Decision Running → Conflict → Private Negotiation → User Approval → Re-Commit → Final Consensus → Participant Receipt → Explorer Verification`

각 전환은 `03-state-machine.md`의 state와 `04-api-contract.md` endpoint를 따라야 한다. Shared Room은 lifecycle의 진행만 반영하며 private route의 성공/실패 이유를 렌더링하지 않는다.
