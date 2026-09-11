# Blockchain Contract와 commitment

Blockchain은 AI의 정답이나 Engine의 계산 정확성을 증명하지 않는다. 승인된 input version, 사용 input set, candidate dataset, Engine identity, final result의 provenance를 운영자와 독립된 public record에 고정한다. P0 Smart Contract는 proxy 없이 immutable deployment다.

## On-chain과 Off-chain 경계

| On-chain public record | Off-chain 전용 데이터 |
|---|---|
| `decision_room_id`, `participant_pseudonym`, `constraint_version`, `condition_commitment`, supersession 관계 | raw `source_text`, private reason, `constraint_value`, salt, `participant_id`, session |
| `input_set_root`, `candidate_dataset_hash`, `engine_version`, `engine_code_hash`, `final_decision_hash`, `decision_commitment` | conflict set, proposal detail, UserApproval audit detail, candidate dataset 원문 |
| block timestamp, `transaction_hash`, contract event | encryption key와 provider credential |

## 정본 serialization과 hash

모든 hash payload는 `protocol:"HUSH"`, `schema_version:"1"` domain separator를 포함한다. public-chain record와 연결되는 payload는 배포가 정해진 뒤 `chain_id`와 `verifying_contract`도 포함해 다른 network/contract에서의 replay를 막는다. `salt`와 bytes 값은 소문자 `0x`-prefixed hex, ID는 UTF-8 string, 정수는 JSON integer로 표현한다. 구현체는 `test-vectors/hash-v1.json`의 canonical bytes와 expected hash를 공통으로 통과해야 한다.

`condition_commitment = keccak256(canonical_json({decision_room_id, participant_pseudonym, constraint_id, constraint_version, constraint_type, priority, constraint_value, salt}))`다. `salt`는 cryptographically random 32-byte 값이며 version마다 새로 생성하고 encrypted off-chain storage에만 둔다. raw deterministic hash를 쓰지 않아 dictionary attack이 가능해지는 것을 금지한다.

`input_set_leaf = keccak256(canonical_json({decision_room_id,decision_run_id,participant_input_id,input_mode,constraint_version_id,condition_commitment}))`다. `constraint_version_id`는 `CONSTRAINED`이면 required이고 `EMPTY`이면 canonical JSON의 `null`이다. leaf는 DecisionRun에 bind되므로 다른 room/run에서 replay할 수 없다. `CONSTRAINED`의 `participant_input_id`는 해당 `ConstraintVersion`에 1:1로 연결된 immutable input ID이고, `EMPTY`의 `participant_input_id`는 explicit empty declaration의 비공개 ID다. P0 `input_set_root`는 frozen roster의 모든 `ParticipantInput` leaf를 byte-lexicographic으로 정렬한 배열의 canonical JSON을 Keccak-256한 값이다. identical leaf가 입력되면 duplicate는 validation failure이며 배열에서 제거하거나 합치지 않는다. participant join 순서나 Constraint 제출 순서는 root에 영향을 주지 않는다. Merkle Tree는 사용하지 않는다.

`final_decision_hash = keccak256(canonical_json({final_decision_id,candidate_id,input_set_root,candidate_dataset_hash,engine_version,engine_code_hash}))`다. Local Demo의 `decision_commitment`는 canonical JSON을 사용한다. EVM record의 `decision_commitment`는 Contract가 `keccak256(abi.encode(keccak256("HUSH_DECISION_V1"), block.chainid, address(this), decision_room_id, input_set_root, candidate_dataset_hash, keccak256(bytes(engine_version)), engine_code_hash, final_decision_hash))`로 직접 계산·검사한다. 따라서 다른 chain 또는 contract record로 replay할 수 없으며 local/on-chain verification mode를 섞지 않는다.

## Smart Contract interface

| Function | purpose·parameters·event·failure semantics |
|---|---|
| `createDecision(decision_room_id)` | Backend Adapter의 authorized relayer가 room registry를 한 번 생성하고 `DecisionCreated`를 emit한다. duplicate는 revert하며 off-chain state를 바꾸지 않는다. |
| `commitCondition(decision_room_id,participant_pseudonym,constraint_version_id,constraint_version,condition_commitment)` | 최초 ConstraintVersion만 기록하고 `ConditionCommitted`를 emit한다. 같은 room/version ID 또는 commitment 재기록은 revert한다. successful mined receipt가 initial version의 `Commitment CONFIRMED` 및 `ACTIVE` 전환 trigger다. |
| `supersedeCondition(decision_room_id,participant_pseudonym,previous_constraint_version_id,previous_constraint_version,previous_condition_commitment,new_constraint_version_id,new_constraint_version,new_condition_commitment)` | successor의 새 commitment와 previous→new 관계를 **하나의 transaction**에서 기록하고 `ConditionSuperseded`를 emit한다. previous record/commitment 불일치, duplicate new version, unauthorized caller는 revert한다. successful mined receipt만 v1 `SUPERSEDED`, v2 `ACTIVE`, v2 Commitment `CONFIRMED`의 off-chain atomic transition trigger다. |
| `finalizeInputSet(decision_room_id,input_set_root,candidate_dataset_hash,engine_version,engine_code_hash)` | Backend Adapter가 frozen run provenance를 한 번 기록하고 `InputSetFinalized`를 emit한다. duplicate/mismatch는 revert한다. successful mined receipt 뒤에만 final decision posting을 허용한다. |
| `commitDecision(decision_room_id,input_set_root,candidate_dataset_hash,engine_version,engine_code_hash,final_decision_hash,decision_commitment)` | finalized input과 동일한 final provenance를 기록하고 `DecisionCommitted`를 emit한다. mismatch/duplicate는 revert하며 receipt는 만들지 않는다. |
| `verifyDecisionRecord(decision_room_id)` | public record를 read-only 반환하며 상태 변경이나 event가 없다. |

`ConditionSuperseded`는 `previous_constraint_version_id`, `previous_constraint_version`, `previous_condition_commitment`, `new_constraint_version_id`, `new_constraint_version`, `new_condition_commitment`을 같은 event/transaction에 포함해야 한다. contract는 raw private data, salt, UserApproval 원문을 저장하지 않는다.

## 게시와 검증 절차

최초 user-confirmed version은 `commitCondition`을 제출한다. 제출 직후 Commitment는 `PENDING`, successful mined receipt면 `CONFIRMED`와 version `ACTIVE`, reverted receipt면 `FAILED`와 version `PENDING_ACTIVATION`이다. successor는 `UserApproval` 뒤 `supersedeCondition` 하나만 제출한다. 이전 version은 해당 transaction이 successful mined 되기 전까지 `ACTIVE`+`CONFIRMED`로 유지한다. mined receipt 후 lifecycle store에서 CAS/database transaction으로 v1 `ACTIVE → SUPERSEDED`, v2 `PENDING_ACTIVATION → ACTIVE`, v2 Commitment `PENDING → CONFIRMED`를 함께 적용한다. reverted receipt면 v1은 유지되고 v2 Commitment만 `FAILED`다. 별도의 successor `commitCondition`이나 사후 `supersedeCondition` transaction은 존재하지 않는다.

Engine output과 고정 dataset이 일치할 때만 `finalizeInputSet`과 `commitDecision`을 호출하며, finalization도 required on-chain record가 `CONFIRMED`일 때만 진행한다.

participant는 receipt의 모든 `participant_inputs` entry를 확인한다. 각 `CONSTRAINED` entry는 자기 `constraint_value`와 salt로 `condition_commitment`를, `EMPTY` entry는 자기 canonical empty payload와 salt로 `condition_commitment`를 로컬 재계산할 수 있다. 이어 각 entry의 run-bound `input_set_leaf`를 재계산하고 모든 내 leaf가 `input_set_leaves`에 존재하는지 확인한다. 전체 leaf set을 byte-lexicographic sort 및 canonical serialize해 `input_set_root`를 재계산한다. P0는 독립 검증을 위해 전체 leaf set을 receipt 수신자에게 제공하지만, raw constraint, private reason, salt, participant identity와 다른 leaf의 직접 mapping은 제공하지 않는다. 이는 제한적인 metadata disclosure이며 소규모 room의 추론 위험을 완전히 없애지 못한다. 마지막으로 explorer/RPC에서 root, dataset hash, Engine identity, `final_decision_hash`, `decision_commitment`을 비교한다.

독립 재현을 위해 receipt에는 content-addressed 또는 immutable release의 `candidate_dataset_uri`, `engine_artifact_uri`, `verification_script_uri`, `engine_git_commit`을 함께 제공한다. `engine_code_hash`는 Git commit 문자열이 아니라 공개한 Engine source archive bytes의 Keccak-256이다. Git commit과 artifact hash는 별도 field로 유지한다.

## Pre-Screening Demo 구현 범위

Demo(`backend/hush/chain.py`)는 위 interface 중 **최종 결정 provenance만** 사용한다:
`createDecision → finalizeInputSet → commitDecision` 3개 transaction을 기본 Ethereum Sepolia
(`chain_id` 11155111)에 기록한다. 배포 레지스트리: `0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8`.
`commitDecision`은 컨트랙트가 `computeDecisionCommitment`로 재계산한 값과 대조한다. 참가자별
`commitCondition` / `supersedeCondition`의 on-chain 기록은 Demo 범위 밖이며 off-chain
lifecycle로만 처리한다.

레지스트리는 `decisionRoomId`마다 write-once이므로, Demo는 reset마다 새 `run_salt`를 만들어
`decision_room_key = keccak256(f"{room_id}:{run_salt}")`로 매 리허설에 새 record를 쓴다.
결정 직후 provenance는 `PENDING`, mined면 `CONFIRMED`, revert면 `FAILED`이고, anchoring은
백그라운드로 수행돼 결정 흐름이 block 확정을 기다리지 않는다. `HUSH_CHAIN_*` 미설정이거나
RPC/tx 실패 시 local verification fallback으로 내려가며 fake transaction/explorer 증거는
만들지 않는다.

## 향후 확장

P1의 Merkle proof는 자신의 `input_set_leaf`, Merkle proof, `input_set_root`만으로 inclusion을 검증하게 하므로 전체 `input_set_leaves` 전달을 제거한다. participant wallet signature와 ZK 만족 증명도 P1이다. public metadata로 인한 소규모 집단 추론 가능성은 P0에서 제거되지 않으므로 UI와 threat model에 명시한다.
