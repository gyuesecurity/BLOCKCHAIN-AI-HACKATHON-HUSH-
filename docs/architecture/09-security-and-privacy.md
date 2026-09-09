# 보안과 프라이버시

Minimum Necessary Disclosure를 기본 규칙으로 한다. API authorization은 “같은 room에 속함”이 아니라 “해당 private object의 owner임”을 요구한다.

| Threat | Impact·Boundary | Mitigation | Residual Risk |
|---|---|---|---|
| Private constraint leakage | 타 participant/운영자 노출 | owner-scoped API, shared safe projection, encrypted storage | 소규모 맥락 추론 |
| Participant enumeration | 초대 밖 identity 노출 | opaque invite/session, generic 404 | room 내 pseudonym 관찰 |
| Cross-participant authorization bypass | 타인의 proposal/receipt 탈취 | every query에 `participant_id` ownership 검사 | 구현 결함 위험 |
| LLM prompt injection | schema/secret 탈취 또는 명령 오염 | untrusted text 분리, schema allowlist, tool 차단 | 외부 provider 처리 위험 |
| Malformed LLM output | 잘못된 Constraint 생성 | strict validation + user confirmation | user 오해 가능성 |
| Commitment / supersession mismatch | successor provenance 없는 off-chain activation 또는 receipt 위조 | new commitment를 담은 single `supersedeCondition`, mined receipt 뒤 atomic CAS, chain event 대조 | 구현 hash bug |
| Replay | accept/commit 재실행 | idempotency key, version/state 검사, contract uniqueness | network retry 지연 |
| Stale ConstraintVersion usage | 승인 전/구 version으로 결정 | `ACTIVE`+`CONFIRMED` eligibility, frozen snapshot, `409 STALE_CONSTRAINT_VERSION` | concurrent UX 혼선 |
| Unauthorized Relaxation approval | user control 상실 | proposal owner session, explicit `UserApproval`, confirmation 뒤 atomic activation/supersession | session 탈취 |
| Blockchain metadata leakage | pseudonym/version 연관 추론 | no raw value/salt, room별 pseudonym, 최소 event | public timing과 소규모 추론 |
| Salt leakage | dictionary attack | CSPRNG 32-byte salt, encrypted storage, log redaction | endpoint compromise |
| Sensitive logging | raw input/secret 유출 | allowlist structured audit, redaction, access control | 운영 실수 |
| Receipt forgery | 거짓 verification 주장 | chain public values와 receipt 비교 | 사용자가 explorer를 확인하지 않을 수 있음 |
| P0 leaf-set metadata disclosure | 다른 leaf의 membership·timing 추론 | raw value/reason/salt 및 identity mapping 미제공, owner-only receipt | 소규모 room 맥락 추론 |
| EMPTY input omission / replay | roster participant가 root에서 빠지거나 다른 run leaf 재사용 | room·run·participant input에 bind된 EMPTY commitment/leaf, frozen roster completeness 검사 | 구현 결함 |
| Decision provenance mismatch | 다른 input/code 결과를 주장 | root/dataset/Engine/final hash를 같은 commitment에 결속 | HUSH가 악성 code를 처음 배포할 위험 |

## 필수 점검

다른 participant가 A의 raw private constraint에 접근하는 endpoint·log·shared event는 없어야 한다. Shared Room API는 participant-specific detail을 반환하지 않아야 한다. on-chain hash는 salt 없는 raw value hash가 아니어야 하며 salt와 raw input은 log에 남기지 않는다.

AI, Engine, Backend, Smart Contract 어느 것도 approval 없이 `HARD` value를 변경하지 않는다. 모든 successor change는 `RelaxationProposal → UserApproval → new ConstraintVersion(PENDING_ACTIVATION) → supersedeCondition(new commitment 포함, PENDING) → successful mined → atomic activation` 순서다. 새 version의 single supersession transaction이 `CONFIRMED`되기 전에는 기존 `ACTIVE` version을 `SUPERSEDED`할 수 없다.

P0 receipt의 `participant_inputs`는 owner의 모든 `CONSTRAINED` input과 필요 시 `EMPTY` input을 표현한다. 전체 `input_set_leaves`는 root 재계산을 위한 제한적 metadata disclosure다. raw constraint, private reason, salt, participant identity와 leaf의 직접 mapping은 공개하지 않는다. P1 Merkle proof는 내 leaf와 proof만 제공해 이 전체 leaf set 전달을 제거한다.
