# HUSH 실행 데모

이 구현은 3~4일 Pre-Screening용 thin vertical slice다. 네 참가자의 고정 fixture를 사용해 `INFEASIBLE → private proposal → user ACCEPT → recalculation → FEASIBLE → receipt verification`을 실제 계산한다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn hush.main:app --app-dir backend --reload
```

공용 화면은 `http://127.0.0.1:8000`, 참가자 개인 화면은 `/participant`, OpenAPI 문서는 `/docs`다. 네 참가자는 서로 다른 브라우저 또는 시크릿 창에서 다음 Demo invite를 사용한다.

| Participant | Invite code | 자연어 입력 예시 |
|---|---|---|
| A | `HUSH-A-2026` | `15,000원 넘는 곳은 부담스러워요` |
| B | `HUSH-B-2026` | `해산물은 못 먹어요` |
| C | `HUSH-C-2026` | `휠체어 경사로가 필요해요` |
| D | `HUSH-D-2026` | `21시 이전에 끝나야 해요` |

현재 자연어 구조화는 외부 LLM이 아니라 허용 schema만 처리하는 deterministic fallback이다. 응답과 화면에 `DEMO_RULE_PARSER`, `is_ai=false`를 표시하며 AI라고 과장하지 않는다.

## 현재 증명하는 것

- 후보 전체에 대한 실제 Hard Constraint 평가
- fixture 데이터에서 최소 가격 완화값 `15000 → 17000` 탐색
- 사용자 승인 전 조건 불변과 승인 후 새 version 계산
- Shared API의 proposal·owner detail 비노출
- 초대 코드로 발급한 random owner-bound Demo session과 shared/private 화면 분리
- 자신의 Condition Commitment와 input leaf 포함 여부 재검증
- dataset, Engine source, input set root, final decision hash와 decision commitment의 Keccak-256 로컬 재검증
- 일반 영수증에서는 salt를 제외하고 인증된 검증용 JSON export에만 자신의 preimage material 포함
- Solidity `HushDecisionRegistry` 컴파일 가능성

## 정직한 한계

- 현재 ledger adapter는 local memory이며 UI에 `Demo local verification — not on-chain`이라고 표시한다.
- invite code는 시연 fixture다. join 뒤 participant session은 매번 새 random token으로 발급되지만 production 인증을 대체하지 않는다.
- 실제 LLM parsing, PostgreSQL persistence, transaction outbox, EVM RPC 배포는 다음 integration 단계다.
- Contract가 아직 testnet에 배포되지 않았으므로 transaction hash나 explorer link를 만들지 않는다.

이 한계를 숨기거나 `on-chain verified`로 표현하지 않는다.
