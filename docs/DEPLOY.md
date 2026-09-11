# Railway 배포

HUSH 데모를 Railway에 올려 공개 URL로 시연하기 위한 절차.
로컬/개발 실행은 [`DEMO-RUNBOOK.md`](DEMO-RUNBOOK.md) §B 참고.

레포에 배포 설정이 이미 있다:

- `Dockerfile` — `$PORT` 존중, `--proxy-headers`, `.[llm,chain,postgres]` 설치
- `railway.json` — Dockerfile 빌더, `/health` 헬스체크, 실패 시 재시작
- `backend/hush/store.py` — Railway가 주입하는 `DATABASE_URL`을 자동 인식 (postgres:// 스킴은 psycopg 드라이버로 변환)

---

## 1. 프로젝트 생성 + 레포 연결

1. https://railway.app 로그인 (GitHub 계정)
2. **New Project** → **Deploy from GitHub repo** → `gyuesecurity/BLOCKCHAIN-AI-HACKATHON-HUSH-` 선택
3. 브랜치: 시연에 쓸 브랜치 지정 (`feat/initial-implementation` 또는 머지 후 `main`)
4. Railway가 `Dockerfile`을 감지해 자동 빌드 시작

## 2. Postgres 추가

1. 프로젝트 캔버스에서 **New** → **Database** → **Add PostgreSQL**
2. 생성되면 앱 서비스가 자동으로 `DATABASE_URL` 참조를 받는다
   - 안 되면: 앱 서비스 → **Variables** → **New Variable** → **Add Reference** → Postgres의 `DATABASE_URL`

## 3. 환경변수 설정

앱 서비스 → **Variables** → 아래 추가 (로컬 `.env`에서 값 복사):

| 변수 | 값 | 필수 |
|------|-----|:---:|
| `HUSH_DEMO_ADMIN_KEY` | 긴 랜덤 문자열 (reset/seed API 보호) | ✅ |
| `HUSH_STATE_KEY` | 로컬 `.env`의 Fernet 키 그대로 | ✅ |
| `GEMINI_API_KEY` | 로컬 `.env` 값 | LLM용 |
| `HUSH_CHAIN_PRIVATE_KEY` | 로컬 `.env` 값 (`0x…`) | 온체인용 |
| `HUSH_CHAIN_CONTRACT_ADDRESS` | `0x946ff260a3F67A37c6D0B60bD2E5db905b499cf8` | 온체인용 |
| `HUSH_CHAIN_RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` | 온체인용 |
| `HUSH_CHAIN_ID` | `11155111` | 온체인용 |

`DATABASE_URL`은 2번에서 자동. `PORT`는 Railway가 자동 주입 — **직접 설정하지 말 것.**

> LLM/온체인 변수를 빼면 그 기능만 fallback된다 (규칙 파서 / `— not on-chain`). 데모 흐름·검증은 그대로.

## 4. 공개 도메인 생성

앱 서비스 → **Settings** → **Networking** → **Generate Domain**
→ `https://____.up.railway.app` 발급.

## 5. 확인

```bash
curl https://____.up.railway.app/health
# {"status":"ok","persistence":"postgresql","at_rest_encryption":"fernet"}
```

- `persistence: postgresql` 이어야 함 (sqlite면 2번 참조가 안 걸린 것)
- `at_rest_encryption: fernet` 이어야 함 (none이면 `HUSH_STATE_KEY` 누락)

브라우저: `https://____/` (공용), `https://____/invite` (QR), 폰으로 QR 스캔.

첫 시연 전 리셋:
```bash
curl -X POST https://____/api/demo/admin/reset -H "X-Demo-Admin-Key: <HUSH_DEMO_ADMIN_KEY>"
```

---

## 운영 메모

- **자동 재배포**: 연결된 브랜치에 push하면 Railway가 다시 빌드·배포
- **환경변수 변경**: 대시보드에서 수정 → 자동 재배포
- **URL은 공개**: 링크를 아는 사람은 접속 가능 (검색 노출은 안 됨). `/invite`가 초대 코드를 노출하므로
  아무나 참가자로 join 가능. 해커톤 fixture라 데이터 위험은 없지만, 남이 결정을 실행하면
  relayer testnet ETH를 소모함 (~0.18 ETH, 100회+ 여유). 걱정되면 시연 직전 배포 / 직후 삭제.
- **비용**: Hobby plan은 사용량 기반. 데모 트래픽이면 무료 크레딧 내. 안 쓸 때 서비스 **Remove** 하면 과금 중단.
- **로그**: 앱 서비스 → **Deployments** → 최신 빌드 → **View Logs** 에서 빌드/런타임 로그 확인.

## 자주 나오는 문제

| 증상 | 원인 / 해결 |
|------|-------------|
| 빌드 실패 `pip install` | 빌드 로그 확인. `[postgres]` extra가 psycopg 빌드에 실패하면 Railway 이미지에 `libpq` 필요 — 이 Dockerfile은 `python:3.12-slim` + `psycopg[binary]`라 보통 OK |
| `/health`가 `persistence: sqlite` | 3번 `DATABASE_URL` 참조 누락. Postgres 서비스의 `DATABASE_URL`을 앱에 Reference로 추가 |
| 502 / 헬스체크 실패 | `PORT`를 수동 설정했는지 확인 (하면 안 됨). 로그에서 uvicorn 바인딩 포트 확인 |
| 온체인이 계속 `— not on-chain` | `HUSH_CHAIN_PRIVATE_KEY` + `HUSH_CHAIN_CONTRACT_ADDRESS` 둘 다 있는지, relayer 잔액 > 0 인지 |
