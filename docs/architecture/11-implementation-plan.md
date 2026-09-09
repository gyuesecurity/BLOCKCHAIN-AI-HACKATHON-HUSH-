# 구현 계획

이 구현 계획은 **서류 심사 통과 후 진행하는 7주 P0 구현**을 설명한다. 3~4일 Pre-Screening Demo의 별도 구현 계획은 [12-pre-screening-demo.md](12-pre-screening-demo.md)에 있으며, 두 계획을 섞지 않는다.

아래는 설계 확정 뒤 만들 vertical slice 순서이며 실제 Issue 생성이나 구현을 뜻하지 않는다.

| Phase | Goal·Dependencies | 예상 module | Acceptance criteria·Tests required |
|---|---|---|---|
| 1 Repository Scaffold | 문서 계약을 반영한 빈 구조 / 없음 | frontend, backend, engine 경계 | 금지된 P1 기능 없음; lint/구조 점검 |
| 2 Canonical Domain Model | 객체·enum·serialization / 02 | domain, persistence mapping | field/state 일치; canonical serialization test vector 통과 |
| 3 Room / Participant | room과 private session / 03,04 | room, auth | cross-owner 접근 차단 test |
| 4 Constraint + AI Parsing | draft→confirm / 06 | constraint, AI adapter | invalid AI와 user 수정 test |
| 5 Decision Engine | deterministic feasibility / 05 | engine, dataset | 다중 Constraint·EMPTY input을 포함한 동일 frozen input의 byte-identical output test |
| 6 Conflict / Minimum Relaxation | private proposal 계산 / 05 | conflict, proposal | no disclosure, ranking, no-auto-change test |
| 7 Private Negotiation | approval과 versioning / 03,04 | approval, version | accept/reject/concurrent/stale test |
| 8 Blockchain Commitment | immutable registry adapter / 07 | contract, adapter | initial `commitCondition`, new commitment을 포함한 single `supersedeCondition`, atomic activation/revert test |
| 9 Participant Receipt / Verification | independent evidence / 07 | receipt, verification UI | 다중 `participant_inputs`, EMPTY leaf, P0 leaf-set root 재계산과 local+public record match/mismatch test |
| 10 Frontend Integration | 세 UI surface / 08 | participant/shared/verification | safe shared response UI test |
| 11 E2E | canonical 4인 흐름 / 전체 | e2e harness | infeasible→accept→final→verify test |
| 12 Demo Hardening | freeze와 fallback / 10 | observability, demo assets | RPC/explorer 장애 rehearsal |

## 권장 작업 단위

`canonical serialization vectors`, `room participant authorization`, `constraint version lifecycle`, `AI schema gateway`, `deterministic candidate evaluator`, `private relaxation router`, `approval compare-and-set`, `Decision Registry adapter`, `receipt verifier`, `shared-safe API projection`, `canonical lifecycle E2E`, `demo fallback rehearsal` 단위로 나누면 이후 GitHub Issue로 바로 옮길 수 있다.

canonical serialization test vector는 최소 하나의 고정 fixture로 `canonical domain payload`, RFC 8785 호환 canonical JSON bytes, salt encoding, hash input bytes, expected `keccak256` result, expected `condition_commitment`를 정의해야 한다. fixture는 `CONSTRAINED`와 `EMPTY`의 `ParticipantInput`, run-bound `input_set_leaf`, 정렬된 `input_set_leaves`, `input_set_root`도 포함해야 한다. Backend, Verification tooling/UI, Blockchain integration layer가 같은 fixture에서 동일 결과를 생성하는 것을 Phase 2와 Phase 8/9의 acceptance criterion으로 검증한다. 이번 문서는 fixture 값이나 test code를 작성하지 않는다.

각 Phase는 이전 Phase의 acceptance criteria와 security test를 통과한 뒤 진행한다. P0가 Week 5 checkpoint에서 안정적이지 않으면 P1 작업을 시작하지 않는다. Engine 또는 immutable contract가 freeze 뒤 변경되면 `engine_code_hash`, deployment address, transaction, receipt와 demo evidence를 모두 다시 생성한다.
