# HUSH 시연 런북

발표 당일 이 문서만 보고 진행. 시스템 설명은 [`DEMO.md`](DEMO.md), 아키텍처는
[`architecture/`](architecture/README.md).

시연 방식은 둘 중 하나:

- **§A 배포된 URL** — 발표자·참가자 모두 설치 없이 브라우저만. 배포됐다면 이 방식.
- **§B 로컬 실행** — 개발·오프라인 대비. 한 대에서 서버, 폰은 같은 Wi-Fi 또는 터널.

두 경우 모두 **§3 시연 순서**는 동일하다.

---

## 이미 공유돼 있는 것 (repo 안)

- 배포된 레지스트리: `0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8`
  (Ethereum Sepolia — https://sepolia.etherscan.io/address/0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8)
- 초대 코드: `HUSH-A-2026` … `HUSH-D-2026` (`/invite` 페이지가 QR로 표시)
- 후보 식당 6곳, 데모 조건 4개 (`backend/hush/fixtures.py`)

## 팀에서 따로 받아야 하는 것 (repo에 없음, gitignored)

| 값 | 용도 | 없으면 |
|----|------|--------|
| `GEMINI_API_KEY` | 실제 LLM 구조화 | 규칙 파서로 fallback (화면에 정직 표기) |
| `HUSH_CHAIN_PRIVATE_KEY` | 온체인 기록용 relayer 키 | LOCAL 검증만 (`— not on-chain`) |
| `HUSH_STATE_KEY` | DB at-rest 암호화 | 평문 저장 + 경고 로그 |

**연습만 할 거면 전부 없어도 된다.** 시연 흐름·검증·변조 탐지까지 그대로 동작하고,
LLM/온체인 부분만 fallback으로 표시된다.

---

## §A 배포된 URL로 시연

1. 팀이 공유한 URL 확인: `https://____.up.railway.app`
2. `https://____/health` → `{"status":"ok","persistence":"postgresql", ...}` 확인
3. 화면:
   - 공용 Decision Room: `https://____/`
   - 참가자 초대 QR: `https://____/invite`
   - 참가자 개인 화면: 폰으로 QR 스캔 (자동으로 `/participant?p=..&code=..` 진입)
4. 깨끗한 상태로 시작:
   ```bash
   curl -X POST https://____/api/demo/admin/reset -H "X-Demo-Admin-Key: <관리자키>"
   ```
5. → **§3**

---

## §B 로컬 실행

### 준비 (한 번만)

```bash
git clone <repo-url>
cd BLOCKCHAIN-AI-HACKATHON-HUSH-

python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Git Bash:
source .venv/Scripts/activate

pip install -e ".[dev,llm,chain]"

# .env 생성 (기본값만으로도 동작)
cp .env.example .env          # Windows: copy .env.example .env
pytest -q                     # 64 passed 확인
```

### `.env` 채우기 — 전부 선택

`cp .env.example .env`만 해도 `HUSH_DEMO_ADMIN_KEY`가 채워져 바로 돌아간다.
풀 데모를 로컬에서 하려면 위 "팀에서 받아야 하는 것"을 `.env`에 추가:

```bash
GEMINI_API_KEY=...
HUSH_STATE_KEY=...            # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
HUSH_CHAIN_PRIVATE_KEY=0x...
HUSH_CHAIN_CONTRACT_ADDRESS=0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8
```

### 서버 켜기

```bash
python -m uvicorn hush.main:app --app-dir backend --env-file .env --port 8000
```

확인: `http://127.0.0.1:8000/health`
→ `persistence`(sqlite/postgresql), `at_rest_encryption`(none/fernet) 표시.

### 화면

| URL | 띄우는 곳 |
|-----|-----------|
| `http://127.0.0.1:8000/` | 프로젝터 (공용 Decision Room) |
| `http://127.0.0.1:8000/invite` | 시연자 노트북 (참가자 QR 4개) |
| `http://127.0.0.1:8000/participant` | 참가자 폰 4대 / 시크릿 창 4개 |

### 폰이 `127.0.0.1`에 못 붙을 때

- 같은 Wi-Fi: 서버 PC IP 확인 (`ipconfig` / `ifconfig` / `ip addr`) → `http://192.168.x.x:8000`
  - 방화벽에서 8000 포트 인바운드 허용 필요할 수 있음
- 다른 네트워크: 터널
  ```bash
  npx cloudflared tunnel --url http://localhost:8000
  # 또는:  ngrok http 8000
  ```
  → 나온 `https://…` URL을 `/invite`에서 사용

### 깨끗한 상태로 시작

```bash
curl -X POST http://127.0.0.1:8000/api/demo/admin/reset -H "X-Demo-Admin-Key: <관리자키>"
```

`<관리자키>` = `.env`의 `HUSH_DEMO_ADMIN_KEY` 값 (`cp .env.example .env` 기본값은
`replace-with-a-random-secret`).

---

## §3 시연 순서 (약 6분, §A·§B 공통)

아래 URL은 §A면 `https://____`, §B면 `http://127.0.0.1:8000`.

### ① 시작 상태 — 공용 화면
- 상태 `COLLECTING`, 참가자 4명, 확정 0
- 대사: **"공용 화면에는 누가 어떤 조건을 냈는지 전혀 보이지 않습니다."**

### ② 참가자 4명 자연어 입력 (폰)
`/invite`의 QR 스캔 → 개인 화면 자동 진입 → **개인 세션 시작** → 자연어 입력 →
**조건 구조화** → 결과 확인 → **해석 결과 확정**

| 참가자 | 입력 | 구조화 결과 |
|--------|------|-------------|
| A | `1인당 15,000원 넘으면 부담스러워요` | `max_price` · **HARD** · 15000 |
| B | `가능하면 해산물은 피하고 싶어요` | `excluded_category` · **SOFT** · seafood |
| C | `휠체어 경사로가 필요해요` | `accessibility_required` · **HARD** |
| D | `21시 이전에 끝나야 해요` | `latest_end_time` · **HARD** · 21:00 |

- 대사: **"`AI 구조화 · gemini-3.5-flash-lite`라고 뜹니다 — 실제 LLM이 자연어를 구조화하고, 사용자가 확인 버튼을 눌러야 확정됩니다."**
- ⚠️ **입력 사이 5초 이상.** Gemini 무료 키 rate limit(429) 시 규칙 파서로 자동 fallback
  (`규칙 파서 (LLM fallback)` 표기 — 거짓말 아님). 불안하면 §5의 seed로 우회.
- 키가 없는 환경이면 처음부터 `규칙 파서`로 표시된다 — 흐름은 동일.

### ③ 공용 화면 → `READY` (4/4)

### ④ 결정 엔진 실행 (아무 참가자나 "결정 엔진 실행")
- 결과 `INFEASIBLE` → 공용 화면 `PRIVATE_ADJUSTMENT_AVAILABLE`
- 대사: **"충돌이 생겼지만 공용 화면은 '누구의 어떤 조건이 문제'인지 안 보여줍니다."**
- B·C·D 폰 "내 상태 새로고침" → 협상안 **없음**
- A 폰에만 → **"15,000원 → 17,000원으로 바꾸면 합의 후보 2곳"**

### ⑤ A가 "ACCEPT"
- 조건 v1 → v2 재커밋, v1은 `SUPERSEDED` 이력

### ⑥ A가 "결정 엔진 실행" 다시
- 결과 `FEASIBLE` → **`restaurant-04` 모두의 식탁 (한식, 17,000원)**
- 대사: **"HARD 조건 통과 후보가 두 곳 남았는데, B의 SOFT 선호 '해산물 싫어요'가 최종 선택을 가릅니다. 선호가 없었다면 해산물집이 뽑혔을 겁니다."**

### ⑦ 영수증 + 검증 (A 폰)
- **영수증 보기** → `ON-CHAIN PROVENANCE` 박스
  - 온체인 활성 시: 처음 `Ethereum Sepolia · PENDING` (~40초) → 다시 누르면 `CONFIRMED`
    + 트랜잭션 3건 (createDecision / finalizeInputSet / commitDecision) 각각 **Etherscan 링크**
  - 온체인 미설정 시: `Demo local verification — not on-chain` (가짜 링크 안 만듦)
- **무결성 검증** → `VERIFIED`
  - 온체인 활성: 체크 **16개** (로컬 10 + 온체인 재조회 6)
  - 미설정: 체크 **10개** (로컬)
- **검증용 JSON 내보내기** → 저장한 파일로 서버 없이 재검증:
  ```bash
  python scripts/verify_receipt.py hush-receipt-A.json      # "status": "VERIFIED"
  ```
- 대사: **"서버를 안 믿어도 됩니다. 영수증만 있으면 누구나, 온체인 기록과 대조해 결과를 검증할 수 있습니다."**

---

## §4 핵심 강조 5가지

1. **자연어 → 구조화**: 실제 Gemini, 확정 전엔 draft (`is_ai=true`)
2. **Privacy**: 공용 화면은 충돌 대상·값·사유 미노출, 협상안은 당사자에게만
3. **Deterministic**: 결과 하드코딩 없음 — 후보 6곳 실제 평가, 완화값도 데이터에서 탐색
4. **SOFT 선호가 결정을 바꿈**: B의 취향 때문에 해산물집 탈락
5. **검증 가능**: 영수증 + 온체인 재조회, 서버 신뢰 불필요

---

## §5 리허설 / 사고 대비

| 상황 | 대응 |
|------|------|
| 처음부터 다시 | `curl -X POST <URL>/api/demo/admin/reset -H "X-Demo-Admin-Key: <키>"` |
| 자연어 입력 건너뛰기 | reset 후 `curl -X POST <URL>/api/demo/admin/seed-confirmed-inputs -H "X-Demo-Admin-Key: <키>"` → 바로 `READY`, ④부터 |
| Gemini 429 / 키 없음 | 그대로 진행 (규칙 파서 fallback, 정직 표기) 또는 위 seed로 우회 |
| 서버 죽음 (로컬) | `--env-file .env`로 재실행 → **진행하던 지점부터 복원** (영구 저장) |
| 온체인 느림 | 정상. PENDING 40초 정도. 결정 흐름은 안 멈춤 |
| 폰 접속 불가 | §B의 "폰이 127.0.0.1에 못 붙을 때" 참고 |

## §6 안 하는 것 (질문 대비)

- 참가자별 condition commitment 온체인 기록 → 최종 결정 커밋 1건만 (P0 범위)
- Merkle proof, 참가자 서명, 다중 방, 운영자 기밀성(TEE/MPC) → P1/P2
- 완화 제안은 현재 가격 조건에만 (시간/카테고리 완화는 미구현)
- 컨트랙트 Etherscan 소스 verify는 별도 (bytecode는 온체인, 소스 대조는 수동)
