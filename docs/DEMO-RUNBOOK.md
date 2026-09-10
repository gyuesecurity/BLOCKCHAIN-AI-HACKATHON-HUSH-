# HUSH 시연 런북

발표 당일 이 문서만 보고 진행할 수 있도록 정리한 순서·대사·복구 절차.
시스템 설명·설치는 [`DEMO.md`](DEMO.md), 아키텍처는 [`architecture/`](architecture/README.md).

---

## 0. 사전 점검 (발표 30분 전)

```bash
cd BLOCKCHAIN-AI-HACKATHON-HUSH-
pip install -e '.[dev,llm,chain]'          # 이미 했으면 생략
pytest -q                                   # 64 passed 확인
python scripts/wallet_balance.py            # Ethereum Sepolia > 0.01 ETH 확인
```

`.env`에 아래가 채워져 있어야 한다 (커밋 안 됨, 개인 보관):

| 변수 | 용도 | 없으면 |
|------|------|--------|
| `GEMINI_API_KEY` | 실제 LLM 구조화 | 규칙 파서로 fallback (정직 표기) |
| `HUSH_DEMO_ADMIN_KEY` | reset / seed API | 관리자 단축키 불가 |
| `HUSH_STATE_KEY` | 방 상태 at-rest 암호화 | 평문 저장 + 경고 |
| `HUSH_CHAIN_PRIVATE_KEY` / `HUSH_CHAIN_CONTRACT_ADDRESS` | 온체인 기록 | LOCAL 검증만 (`— not on-chain`) |

배포된 레지스트리: `0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8`
(Ethereum Sepolia, https://sepolia.etherscan.io/address/0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8)

---

## 1. 서버 켜기

```bash
python -m uvicorn hush.main:app --app-dir backend --env-file .env --port 8000
```

`--env-file .env` 필수. 확인: `http://127.0.0.1:8000/health`
→ `{"status":"ok","persistence":"sqlite","at_rest_encryption":"fernet"}`

깨끗한 상태에서 시작하려면:

```bash
curl -X POST http://127.0.0.1:8000/api/demo/admin/reset -H "X-Demo-Admin-Key: <HUSH_DEMO_ADMIN_KEY>"
```

## 2. 화면 배치

| URL | 띄우는 곳 |
|-----|-----------|
| `http://127.0.0.1:8000/` | 프로젝터 (공용 Decision Room) |
| `http://127.0.0.1:8000/invite` | 시연자 노트북 (참가자 QR 4개) |
| `http://127.0.0.1:8000/participant` | 참가자 폰 4대 또는 시크릿 창 4개 |

폰이 `127.0.0.1`에 못 붙으면:
- 같은 Wi-Fi: `ipconfig`로 PC IP 확인 → `http://192.168.x.x:8000`
- 아니면: `cloudflared tunnel --url http://localhost:8000` → 나온 공개 URL 사용

---

## 3. 시연 순서 (약 6분)

### ① 시작 상태 — 공용 화면
- 상태 `COLLECTING`, 참가자 4명, 확정 0
- 대사: **"공용 화면에는 누가 어떤 조건을 냈는지 전혀 보이지 않습니다."**

### ② 참가자 4명 자연어 입력 (폰)
QR 스캔 → 개인 화면 자동 진입 → **개인 세션 시작** → 자연어 입력 → **조건 구조화** → **해석 결과 확정**

| 참가자 | 입력 | 구조화 결과 |
|--------|------|-------------|
| A | `1인당 15,000원 넘으면 부담스러워요` | `max_price` · **HARD** · 15000 |
| B | `가능하면 해산물은 피하고 싶어요` | `excluded_category` · **SOFT** · seafood |
| C | `휠체어 경사로가 필요해요` | `accessibility_required` · **HARD** |
| D | `21시 이전에 끝나야 해요` | `latest_end_time` · **HARD** · 21:00 |

- 대사: **"입력창에 `AI 구조화 · gemini-3.5-flash-lite`라고 뜹니다 — 실제 LLM이 자연어를 구조화하고, 사용자가 확인 버튼을 눌러야 확정됩니다."**
- ⚠️ **입력 사이 5초 이상 간격.** Gemini 무료 키 rate limit(429)에 걸리면 규칙 파서로 자동 fallback (`규칙 파서 (LLM fallback)` 표기 — 거짓말 아님). 불안하면 3-B 우회 사용.

### ③ 공용 화면 → `READY` (4/4)

### ④ 결정 엔진 실행 (아무 참가자나 "결정 엔진 실행")
- 결과 `INFEASIBLE` → 공용 화면 `PRIVATE_ADJUSTMENT_AVAILABLE`
- 대사: **"충돌이 생겼지만 공용 화면은 '누구의 어떤 조건이 문제'인지 안 보여줍니다."**
- B·C·D 폰에서 "내 상태 새로고침" → 협상안 **없음**
- A 폰에만 → **"15,000원 → 17,000원으로 바꾸면 합의 후보 2곳"**

### ⑤ A가 "ACCEPT"
- 조건 v1 → v2 재커밋, v1은 `SUPERSEDED` 이력으로 남음

### ⑥ A가 "결정 엔진 실행" 다시
- 결과 `FEASIBLE` → **`restaurant-04` 모두의 식탁 (한식, 17,000원)**
- 대사: **"HARD 조건 통과 후보가 두 곳 남았는데, B의 SOFT 선호 '해산물 싫어요'가 최종 선택을 가릅니다. 선호가 없었다면 해산물집이 뽑혔을 겁니다."**

### ⑦ 영수증 + 검증 (A 폰)
- **영수증 보기** → `ON-CHAIN PROVENANCE` 박스
  - 처음 `Ethereum Sepolia · PENDING` (~40초)
  - 다시 누르면 `CONFIRMED` + 트랜잭션 3건 (createDecision / finalizeInputSet / commitDecision) 각각 **Etherscan 링크**
- **무결성 검증** → `VERIFIED`, 체크 **16개** 전부 통과
  - 로컬 10개 + 온체인 6개 (레지스트리를 다시 읽어 receipt와 대조)
- **검증용 JSON 내보내기** → 저장한 파일로 서버 없이 재검증:
  ```bash
  python scripts/verify_receipt.py hush-receipt-A.json      # "status": "VERIFIED"
  ```
- 대사: **"서버를 안 믿어도 됩니다. 영수증만 있으면 누구나, 온체인 기록과 대조해 결과를 검증할 수 있습니다."**

---

## 4. 핵심 강조 5가지

1. **자연어 → 구조화**: 실제 Gemini, 확정 전엔 draft (`is_ai=true`)
2. **Privacy**: 공용 화면은 충돌 대상·값·사유 미노출, 협상안은 당사자에게만
3. **Deterministic**: 결과 하드코딩 없음 — 후보 6곳 실제 평가, 완화값도 데이터에서 탐색
4. **SOFT 선호가 결정을 바꿈**: B의 취향 때문에 해산물집 탈락
5. **검증 가능**: 영수증 + 온체인 재조회 16개 항목, 서버 신뢰 불필요

---

## 5. 리허설 / 사고 대비

| 상황 | 대응 |
|------|------|
| 처음부터 다시 | `curl -X POST .../api/demo/admin/reset -H "X-Demo-Admin-Key: <키>"` |
| 자연어 입력 건너뛰기 | reset 후 `curl -X POST .../api/demo/admin/seed-confirmed-inputs -H "X-Demo-Admin-Key: <키>"` → 바로 `READY`, ④부터 |
| Gemini 429 | 그대로 진행(규칙 파서 fallback, 정직 표기) 또는 위 seed로 우회 |
| 서버 죽음 | `--env-file .env`로 재실행 → **진행하던 지점부터 복원** (영구 저장) |
| 온체인 느림 | 정상. PENDING 40초 정도. 그동안 결정 흐름은 안 멈춤 |
| 폰 접속 불가 | PC IP 또는 cloudflared 터널 |

## 6. 안 하는 것 (질문 대비)

- 참가자별 condition commitment 온체인 기록 → 최종 결정 커밋 1건만 (P0 범위)
- Merkle proof, 참가자 서명, 다중 방, 운영자 기밀성(TEE/MPC) → P1/P2
- 완화 제안은 현재 가격 조건에만 (시간/카테고리 완화는 미구현)
