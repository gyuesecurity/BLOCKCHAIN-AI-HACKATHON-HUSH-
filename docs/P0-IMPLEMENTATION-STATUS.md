# 7주 P0 구현 상태

이 문서는 `docs/architecture/00-scope.md`~`11-implementation-plan.md`의 P0 계약을 현재 코드와 연결한다. 기존 `/api/demo/*` 사전심사 흐름은 그대로 유지하고, 정본 P0는 `/rooms/*`와 `/p0*`에 별도로 구현한다.

| 영역 | 구현 | 검증 |
|---|---|---|
| 다중 방·2~20인 roster·opaque session | 완료 | room isolation, restart persistence, cross-owner 404 |
| 자연어 AI 구조화·직접 수정·다중 조건·EMPTY | 완료 | strict five-type schema, user-confirmed input, canonical EMPTY vector |
| deterministic Engine·복수 HARD/SOFT | 완료 | 가격·이동·종료 시간 최소 완화와 deterministic tie-break test |
| private proposal·승인·version supersession | 완료 | owner routing, stale protection, reject/accept, predecessor preservation |
| condition/final on-chain provenance | 완료 | initial commit, atomic supersede, final anchor, read-only public verification |
| 실패 복구 | 완료 | durable idempotency, immutable attempt history, condition/final explicit retry, response-loss recovery |
| Participant Receipt·독립 검증 | 완료 | CONSTRAINED/EMPTY leaf, input root, dataset/engine/final hash, public chain mismatch |
| 세 UI surface | 완료 | `/p0`, `/p0-room`, `/p0-verify`; shared 화면은 safe projection만 사용 |
| 저장·보안 기본선 | 완료 | SQLite/Postgres, Fernet at rest, session ownership, request ID, security headers |

현재 체인 어댑터는 요청 안에서 mined receipt를 기다리는 동기 방식이다. 따라서 명세의 `PENDING` 상태는 내부 전이로 존재하지만 HTTP `202` polling UX는 제공하지 않는다. 한 Railway worker에서는 안전하게 동작하며, 여러 backend worker로 수평 확장할 때는 DB row lock/outbox worker를 추가해야 한다. 이는 해커톤 단일 서비스 배포에는 필요하지 않지만 production scale-out 전 필수다.

검증 명령:

```bash
PYTHON_BIN=.venv/bin/python ./scripts/check.sh
```
