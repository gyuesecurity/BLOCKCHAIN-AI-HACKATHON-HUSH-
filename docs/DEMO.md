# HUSH 실행 데모

이 구현은 3~4일 Pre-Screening용 thin vertical slice다. 네 참가자(A `HARD` 가격, B `SOFT` 음식 선호, C `HARD` 접근성, D `HARD` 종료시간)의 고정 fixture를 사용해 `INFEASIBLE → private proposal → user ACCEPT → recalculation → FEASIBLE(SOFT 선호로 tie-break) → receipt verification`을 실제 계산한다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,llm,chain]'   # 실제 Gemini + EVM testnet 경로 포함
uvicorn hush.main:app --app-dir backend --reload
```

`.[dev]`만 설치하면 `google-genai`가 없어 자연어 구조화가 규칙 파서로만 동작한다(`is_ai=false`).
실제 Gemini 데모에는 `.[llm]`과 `GEMINI_API_KEY`가 필요하다. 무료 티어 키는 rate limit(429)이
낮아 4명 입력을 몰아서 넣으면 일부가 규칙 파서로 fallback할 수 있다(`llm_fallback=true`로 정직하게 표기).
입력을 몇 초씩 띄우거나 유료 키를 쓰면 안정적이다.

공용 화면은 `http://127.0.0.1:8000`, 참가자 개인 화면은 `/participant`, OpenAPI 문서는 `/docs`다.
`/invite` 페이지에 4명분 QR이 있다 — 각자 휴대폰으로 자기 QR을 스캔하면 `/participant?p=..&code=..`가
열리며 참가자·초대 코드가 자동 입력되고 바로 join된다. 4대 휴대폰 데모는 서버를 LAN IP나 터널
(ngrok/cloudflared)로 노출한 뒤 `/invite`를 띄워 스캔하면 된다. QR 없이 서로 다른 브라우저/시크릿
창에서 아래 코드를 직접 입력해도 된다.

| Participant | Invite code | 자연어 입력 예시 |
|---|---|---|
| A | `HUSH-A-2026` | `15,000원 넘는 곳은 부담스러워요` (→ `max_price` `HARD`) |
| B | `HUSH-B-2026` | `가능하면 해산물은 피하고 싶어요` (→ `excluded_category` `SOFT`) |
| C | `HUSH-C-2026` | `휠체어 경사로가 필요해요` (→ `accessibility_required` `HARD`) |
| D | `HUSH-D-2026` | `21시 이전에 끝나야 해요` (→ `latest_end_time` `HARD`) |

`가능하면 / 가급적 / 되도록 / 선호` 같은 뉘앙스는 `SOFT`, 그 외에는 `HARD`로 구조화한다(규칙 파서·Gemini 동일).

## 자연어 구조화 (AI)

`GEMINI_API_KEY`(또는 `GOOGLE_API_KEY`)가 설정돼 있으면 자연어 입력을 실제 Google Gemini로 구조화한다.

```bash
pip install -e '.[llm]'
export GEMINI_API_KEY=...            # https://aistudio.google.com/apikey
# HUSH_LLM_MODEL 기본값 gemini-3.5-flash-lite
# HUSH_LLM_ENABLED=false 로 키가 있어도 강제 비활성
```

Gemini structured output(`response_schema` = Pydantic + `response_mime_type="application/json"`)으로 구조화한다.

- AI는 자연어를 허용 schema(`max_price` · `excluded_category` · `accessibility_required` · `latest_end_time`)의
  draft candidate로 변환하고 한국어로 해석만 설명한다. 최종 결정·조건 완화·자동 승인은 하지 않는다
  (`docs/architecture/06-ai-boundary.md`).
- 사용자 입력은 `<participant_input>`으로 감싸 untrusted 데이터로 전달하고, 모델 출력은
  `backend/hush/llm.py`의 type allowlist · 값 범위 · 시간 형식 검증을 통과해야 draft가 된다.
- LLM 성공 시 응답·화면에 `parser_mode="LLM"`, `is_ai=true`, `model`을 표시한다.
- 키가 없거나 API 오류·schema 위반·거부 시에는 규칙 기반 parser로 자동 fallback하며
  `parser_mode="DEMO_RULE_PARSER"`, `is_ai=false`, `llm_fallback=true`를 표시한다. AI라고 과장하지 않는다.
- 원문이 외부 LLM provider로 전송된다는 점은 UI 및 `docs/architecture/09-security-and-privacy.md`에 고지돼 있다.

## On-chain provenance (선택)

`HUSH_CHAIN_PRIVATE_KEY`와 `HUSH_CHAIN_CONTRACT_ADDRESS`가 설정되면 **최종 결정 커밋**을
EVM testnet(기본 Base Sepolia)에 기록한다. 범위는 Demo-04의 최소치다 — `createDecision →
finalizeInputSet → commitDecision` 3개 트랜잭션. 참가자별 condition commitment는 이 데모에서는
off-chain에 둔다.

```bash
pip install -e '.[chain]'
python scripts/new_wallet.py        # testnet 전용 relayer 지갑 → 출력 주소를 faucet에서 충전
#   Base Sepolia faucet: https://portal.cdp.coinbase.com/products/faucet
python scripts/deploy_contract.py   # 레지스트리 1회 배포 → HUSH_CHAIN_CONTRACT_ADDRESS 출력
export HUSH_CHAIN_RPC_URL=https://sepolia.base.org
export HUSH_CHAIN_PRIVATE_KEY=0x...          # testnet 전용, 커밋 금지
export HUSH_CHAIN_CONTRACT_ADDRESS=0x...
uvicorn hush.main:app --app-dir backend
```

- 컨트랙트는 provenance만 저장한다. raw constraint·salt·participant identity는 올리지 않는다.
- on-chain `decision_commitment`는 컨트랙트가 `DECISION_DOMAIN + chainid + address(this) + …`로
  **직접 재계산·대조**한다. 다른 chain/contract로 replay 불가.
- 결정 직후 provenance는 `PENDING`, mined되면 `CONFIRMED`(receipt에 tx hash·basescan link),
  revert면 `FAILED`. 이 동안 결정 흐름은 블록 확정을 기다리지 않는다(백그라운드 anchor).
- 레지스트리는 room 키마다 write-once라, 데모 reset마다 새 `run_salt`로 새 record를 만든다.
- 키/주소가 없거나 RPC 실패 시 자동으로 local verification fallback이며 `— not on-chain`으로
  표시한다. **fake transaction hash나 fake explorer link는 만들지 않는다.**
- `verify`는 on-chain이 `CONFIRMED`면 레지스트리를 다시 읽어 `decision_commitment` /
  `input_set_root` / `final_decision_hash` / dataset·engine hash 일치를 추가 확인한다.

## 현재 증명하는 것

- 후보 6곳 전체에 대한 실제 Hard Constraint 평가
- fixture 데이터에서 최소 가격 완화값 `15000 → 17000` 탐색
- 완화 후 HARD 조건을 모두 통과한 후보가 2곳 남고, B의 `SOFT` 음식 선호가 최종 선택을 실제로 바꿈(선호 없으면 `restaurant-01` 해산물, 선호 반영 시 `restaurant-04`)
- 사용자 승인 전 조건 불변과 승인 후 새 version 계산
- Shared API의 proposal·owner detail 비노출
- 초대 코드로 발급한 random owner-bound Demo session과 shared/private 화면 분리
- 자신의 Condition Commitment와 input leaf 포함 여부 재검증
- dataset, Engine source, input set root, final decision hash와 decision commitment의 Keccak-256 로컬 재검증
- 일반 영수증에서는 salt를 제외하고 인증된 검증용 JSON export에만 자신의 preimage material 포함
- Solidity `HushDecisionRegistry` 컴파일, 그리고 (설정 시) Base Sepolia에 최종 결정 커밋 실제 기록

## 정직한 한계

- chain 미설정 시 ledger adapter는 local memory이며 UI에 `Demo local verification — not on-chain`이라고 표시한다.
- on-chain은 **최종 결정 커밋 1건**만 기록한다. 참가자별 condition commitment on-chain 기록은 P0 범위다.
- 방 상태는 재시작에도 유지된다: 기본 SQLite(`hush-demo.db`), `HUSH_DATABASE_URL`로 Postgres 전환.
  `HUSH_STATE_KEY`(Fernet)가 있으면 저장 blob 전체가 at-rest 암호화된다(salt·원값·세션 토큰·원문 포함).
  키가 없으면 평문 저장 + 경고 로그.
- invite code는 시연 fixture다. join 뒤 participant session은 매번 새 random token으로 발급되지만 production 인증을 대체하지 않는다.
- 자연어 구조화는 `GEMINI_API_KEY`가 있으면 실제 Google Gemini, 없으면 규칙 기반 parser로 동작한다.
- chain이 미설정이거나 RPC/tx가 실패하면 transaction hash나 explorer link를 만들지 않는다.

이 한계를 숨기거나 `on-chain verified`로 표현하지 않는다.
