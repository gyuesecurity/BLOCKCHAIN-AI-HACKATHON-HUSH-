# 오류와 fallback

실패는 승인된 private condition을 지우거나 state를 모호하게 만들면 안 된다. 모든 retry는 idempotency와 current state를 다시 검사한다.

| Failure | User-visible behavior | Retry·State preservation·Fallback | Continue? |
|---|---|---|---|
| LLM timeout / unavailable | AI 처리 지연 또는 불가 | bounded retry, input draft 보존, direct structured input | 이미 확정된 조건이면 가능 |
| LLM invalid JSON | 해석 불가 안내 | raw/model output 격리, 재parse 또는 직접 입력 | 가능 |
| Decision Engine error | 계산 실패 안내 | same immutable snapshot 재시도, run=`FAILED` | 새 run 전까지 불가 |
| No feasible solution | generic private conflict | proposal 탐색, 원 conditions 보존 | negotiation으로 가능 |
| No valid relaxation | 합의 불가 안내 | P0에서는 room=`CLOSED`; 새 조건은 새 DecisionRoom에서 제출 | 자동 진행 불가 |
| Database error | 저장 실패 안내 | transaction rollback, client 재시도 | 안전 저장 전 불가 |
| Blockchain RPC failure | commitment pending 안내 | initial은 `commitCondition`, successor는 single `supersedeCondition`을 outbox로 재시도; 기존 `ACTIVE`+`CONFIRMED` version 보존 | replacement activation/finalization 불가 |
| Transaction pending | `Commitment=PENDING` 표시 | receipt polling, 같은 tx 재방송 금지; successor는 `PENDING_ACTIVATION` 유지 | 조건 수집 가능, final commit 대기 |
| Transaction reverted | on-chain 기록 실패 | Commitment=`FAILED` 보존, revert reason 기록; successor의 predecessor는 유지, 명시적 재시도는 새 attempt 생성 | 기존 input으로 계속 가능, replacement/final 불가 |
| Explorer unavailable | explorer 확인 불가 | RPC/contract read와 tx hash 제공, 사전 capture는 demo backup | HUSH processing 가능 |
| Client disconnect | 요청 상태 확인 필요 | idempotency key로 결과 조회 | 가능 |
| Duplicate request | 기존 결과 반환 | 같은 key/body replay | 가능 |
| Stale version / roster change | 최신 version 또는 room 재준비 안내 | `409`, frozen run 보존; `READY` 뒤 join/leave 차단 | 새 run 전까지 불가 |
| Concurrent approval | 이미 처리됨 안내 | atomic compare-and-set, 최초 approval만 유효 | 가능 |

Blockchain failure는 `ConstraintVersion`이나 `UserApproval`을 삭제하지 않는다. successor `supersedeCondition`이 `PENDING`/`FAILED`인 version은 `PENDING_ACTIVATION`으로 남고 다음 `DecisionRun` input이 될 수 없다. 기존 `ACTIVE`+`CONFIRMED` version은 유지되며 on-chain supersession provenance도 생성되지 않는다. 재시도는 실패 `Commitment` record를 덮지 않고 새 attempt 및 새 single supersession transaction을 만든다. Engine failure와 infeasibility는 구분한다. 전자는 계산 failure, 후자는 유효 계산 결과다.
