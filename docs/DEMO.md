# HUSH 실행 데모

이 구현은 3~4일 Pre-Screening용 thin vertical slice다. 네 참가자의 고정 fixture를 사용해 `INFEASIBLE → private proposal → user ACCEPT → recalculation → FEASIBLE → receipt verification`을 실제 계산한다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn hush.main:app --app-dir backend --reload
```

`http://127.0.0.1:8000`에서 단계별 버튼을 누른다. OpenAPI 문서는 `/docs`에서 볼 수 있다.

## 현재 증명하는 것

- 후보 전체에 대한 실제 Hard Constraint 평가
- fixture 데이터에서 최소 가격 완화값 `15000 → 17000` 탐색
- 사용자 승인 전 조건 불변과 승인 후 새 version 계산
- Shared API의 proposal·owner detail 비노출
- owner-bound Demo session을 통한 private surface 분리
- dataset, Engine source, input set root의 Keccak-256 로컬 재검증
- Solidity `HushDecisionRegistry` 컴파일 가능성

## 정직한 한계

- 현재 ledger adapter는 local memory이며 UI에 `Demo local verification — not on-chain`이라고 표시한다.
- `demo-session-a` 같은 session은 시연용 고정 값이다. 실제 배포에서는 join 때 생성하는 고엔트로피 opaque session으로 교체해야 한다.
- 자연어 LLM parsing, PostgreSQL persistence, transaction outbox, EVM RPC 배포는 다음 integration 단계다.
- Contract가 아직 testnet에 배포되지 않았으므로 transaction hash나 explorer link를 만들지 않는다.

이 한계를 숨기거나 `on-chain verified`로 표현하지 않는다.
