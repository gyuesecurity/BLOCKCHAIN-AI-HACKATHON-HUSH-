# Pre-Screening Demo Architecture

## 1. 위치와 목적

**Stage A — Pre-Screening Demo**는 서류 심사 전 3~4일 동안 만드는 실제 동작 데모다. 이는 P0를 대체하거나 P0 범위를 축소하는 별도 임시 제품이 아니다. 계획된 **Stage B — 7-week P0**의 사용자 경험과 핵심 기술 흐름을 심사위원이 짧은 시연에서 이해하도록 하는 **thin vertical slice**다.

제품 요구사항의 정본은 [HUSH-project-plan.md](../product/HUSH-project-plan.md)이다. P0의 canonical 모델·lifecycle·API·Engine·AI·blockchain·privacy 계약은 `00`~`11` 문서에 계속 존재하며, Demo가 일부를 구현하지 않는 것은 그 계약을 변경하거나 약화하지 않는다.

| Stage | 기간 | 목적 | 구현 기준 |
|---|---:|---|---|
| Stage A — Pre-Screening Demo | 3~4일 | 핵심 아이디어와 경험을 안정적으로 시연 | 이 문서의 대표 happy path |
| Stage B — P0 | 심사 통과 후 7주 | HUSH 핵심 제품 범위 완성 | 기존 `00`~`11`의 full canonical contract |
| Stage C — P1 / P2 | 이후 | optional / future 확장 | 기존 P1/P2 정의 유지 |

## 2. Demo 성공 메시지와 원칙

시연 후 심사위원은 다음을 실제 동작으로 확인할 수 있어야 한다.

1. 참가자는 서로의 raw private constraint나 private reason을 볼 필요가 없다.
2. AI는 자연어를 structured constraint 후보로 만들고, 사용자가 이를 수정·승인한다.
3. deterministic Decision Engine이 실제 입력과 고정 Candidate Dataset으로 feasibility와 결과를 계산한다.
4. 충돌 시 Engine이 실제 constraint evaluation에서 representative relaxation candidate를 식별하고, 해당 participant에게만 제안한다. Day 2 PM cutline 전에는 generalized numeric minimum-relaxation search를 사용하며, cutline fallback에서는 검증된 Demo representative relaxation rule만 사용한다.
5. `ACCEPT` 또는 `KEEP`는 사용자 행동이며, 승인 뒤에만 재계산되어 새 final decision이 나온다.
6. commitment, receipt, verification evidence로 “내 승인 입력이 결과 provenance에 연결된다”는 Web3 가치를 보인다.

Demo도 아래 P0 원칙을 보존한다.

| Principle | Demo rule | P0 reference |
|---|---|---|
| AI boundary | AI는 parsing·설명·협상 문구만 담당하고 final decision, 자동 변경, 자동 approval을 하지 않는다. | [06-ai-boundary.md](06-ai-boundary.md) |
| User control | structured interpretation의 확정과 relaxation의 `ACCEPT`/`KEEP`는 항상 해당 사용자의 명시적 action이다. | [03-state-machine.md](03-state-machine.md), [04-api-contract.md](04-api-contract.md) |
| Decision authority | feasibility, conflict, relaxation amount, final selection은 deterministic Engine이 계산한다. | [05-decision-engine.md](05-decision-engine.md) |
| Privacy | shared view와 다른 participant private view에는 raw constraint, private reason, owner mapping을 보내거나 표시하지 않는다. | [08-frontend-flow.md](08-frontend-flow.md), [09-security-and-privacy.md](09-security-and-privacy.md) |
| Verification honesty | real chain/RPC evidence와 local/mock/simulated evidence를 UI에서 명확히 구분한다. | [07-blockchain-contract.md](07-blockchain-contract.md) |

## 3. Canonical Demo scenario

대표 scenario는 제품 기획서의 **친구 4명의 저녁 장소 결정**이다. Candidate Dataset은 5~10개의 고정·versioned 식당 후보를 사용해도 된다. 단 결과는 문자열 hard-code가 아니라 아래 입력에 대해 Engine이 실제로 hard filtering, soft scoring, feasibility와 relaxation을 계산한 결과여야 한다.

| Participant | Private demo input | Demo structured form | Visibility |
|---|---|---|---|
| A | “나는 15,000원 넘으면 부담스러워.” | `max_price`, `LTE`, `15000`, `HARD` | A private only |
| B | “고기 먹고 싶어.” | category/meat soft preference | B private only |
| C | “역에서 가까운 곳이면 좋겠어.” | supported travel/access constraint or preference | C private only |
| D | “특정 시간 전에는 끝나야 해.” | `latest_end_time`, `HARD` | D private only |

Dataset은 첫 실행에서 네 participant의 active hard constraints를 동시에 만족하는 후보가 없도록 고정한다. Conflict Analyzer는 실제 candidate별 constraint evaluation에서 A의 `max_price`가 Demo 대상 numeric relaxation candidate임을 식별한다. generalized engine path에서는 **15,000 → 17,000 KRW**의 minimum relaxation을 dataset 기반으로 계산한다. Day 2 PM fallback path에서는 fixture로 사전 검증한 **Demo representative relaxation rule**인 `A.max_price: 15000 → 17000` proposal만 고정할 수 있다. 어느 path든 B와 C의 선호는 feasible 후보의 soft score와 deterministic tie-break에 사용하며, 화면 문구는 실제 Engine 결과와 일치해야 한다.

대표 흐름은 다음이며 발표 중 reset 후 반복 실행 가능해야 한다.

```text
Decision Room → 4 Participants Join → Private Constraint Input
→ AI Structuring → User Confirmation → Demo Commitment
→ Decision Engine → NO FEASIBLE SOLUTION → Conflict Detection
→ Minimum Relaxation → Private Negotiation → A: ACCEPT
→ constraint version change → Recalculation → Final Decision
→ Participant Receipt → Verification
```

첫 계산의 shared view는 예를 들어 다음만 보인다.

```text
NO FEASIBLE SOLUTION
Conflict detected
Raw private conditions shared: NO
```

A의 private view에만 다음처럼 제안한다. 다른 화면에는 A의 identity, type, 원값, 제안값, private reason을 표시하지 않는다.

```text
15,000원 → 17,000원으로 완화하면 합의 가능한 후보가 생깁니다.
[ACCEPT] [KEEP]
```

`ACCEPT` 뒤 Engine은 변경된 사용자 승인 입력으로 다시 실행한다. Final shared view는 `Final Decision`, `Hard Constraints satisfied`, `User-approved relaxation`, `Raw private conditions shared: NO`, 그리고 integrity/verification 상태만 보여 준다.

## 4. Demo 구현 범위와 P0 대응

| Demo capability | 실제 Demo 동작 | 축소한 P0 capability / reference |
|---|---|---|
| Decision Room | Demo room 하나와 4 participant 상태, participant-private/shared view를 제공한다. QR join은 시간이 허용될 때만 하고, 아니면 deterministic demo session을 쓴다. | room·participant session: [02](02-domain-model.md), [03](03-state-machine.md), [04](04-api-contract.md), [08](08-frontend-flow.md) |
| Private input | 각 participant가 자기 자연어 constraint를 제출하며 다른 participant raw input은 조회·렌더링 불가다. | private ownership/privacy: [04](04-api-contract.md), [08](08-frontend-flow.md), [09](09-security-and-privacy.md) |
| AI structuring | 최소 한 개 이상 자연어를 supported structured candidate로 변환하고, 수정 및 confirm action 전에는 Engine input이 되지 않는다. AI 실패 시 직접 structured input fallback을 둔다. | AI schema/user confirmation: [06](06-ai-boundary.md) |
| Demo commitment | confirm된 canonical representation과 random salt에서 `Keccak-256` commitment를 만든다. raw input, value, salt를 shared/on-chain public payload에 넣지 않는다. | Condition Commitment: [07](07-blockchain-contract.md) |
| Decision Engine | fixed dataset을 실제 hard-filter하고, soft preference score와 deterministic candidate-id tie-break로 선택한다. 첫 결과는 input에 따라 `INFEASIBLE`이다. | engine authority/determinism: [05](05-decision-engine.md) |
| Conflict detection | infeasible일 때 actual candidate별 hard-constraint evaluation과 elimination trace에서 representative conflict / Demo 대상 numeric relaxation candidate를 식별하되 shared view에는 generic status만 출력한다. 이 실제 evaluation은 fallback에서도 유지한다. | private conflict routing: [05](05-decision-engine.md), [08](08-frontend-flow.md) |
| Minimum relaxation | 정상 path에서는 numeric `max_price` one-constraint case에서 dataset의 가능한 bound 중 최소 loosened value를 계산한다. Day 2 PM cutline fallback에서는 fixture로 검증된 `A.max_price: 15000 → 17000` **Demo representative relaxation rule** proposal만 사용하며, 범용 solver 완성을 주장하지 않는다. | P0 relaxation semantics: [00](00-scope.md), [05](05-decision-engine.md) |
| Private negotiation | proposal은 target participant private surface에만 route하고, AI는 Engine proposal을 설명만 한다. | proposal/AI boundary: [04](04-api-contract.md), [05](05-decision-engine.md), [06](06-ai-boundary.md), [08](08-frontend-flow.md) |
| User approval + recalculation | `ACCEPT`/`KEEP`가 실제 interaction이다. `ACCEPT` 뒤에만 demo constraint version과 commitment evidence를 갱신하고 Engine을 재실행한다. | approval/versioning: [03](03-state-machine.md), [04](04-api-contract.md), [07](07-blockchain-contract.md) |
| Receipt + verification | participant별 receipt가 decision ID, own commitment/input evidence, final decision, verification status, transaction 또는 demo evidence, `VERIFY` action을 제공한다. | receipt and independent verification: [02](02-domain-model.md), [04](04-api-contract.md), [07](07-blockchain-contract.md), [08](08-frontend-flow.md) |

## 5. Scope Matrix

| Capability | Pre-Screening Demo | 7-week P0 |
|---|---|---|
| Decision Room | Simplified single demo room | Full P0 |
| 4 participant flow | Required | Required |
| Private Input | Required | Full |
| AI Structuring | Required | Full |
| User Confirmation | Required | Full |
| Constraint types | Demo subset | P0 schema |
| Decision Engine | Real, demo dataset | Full P0 |
| Conflict Detection | Representative | Full P0 |
| Minimum Relaxation | Numeric representative case | P0 |
| Private Negotiation | Required | Full |
| User Approval | Required | Full |
| Commitment | Minimal real hash | Full lifecycle |
| Blockchain | Minimal proof path preferred | Full P0 |
| Versioned Re-Commit | Simplified demo semantics after user accept | Full `supersedeCondition` lifecycle |
| Participant Receipt | Demo verification | Full P0 receipt |
| Independent Verification | Core concept demonstrated | Full P0 |
| EMPTY input edge case | Not required for demo | Required |
| Multiple constraints edge cases | Limited | Required |
| Retry / recovery | Minimal | Full P0 |
| ZK | Excluded | P1 |
| Merkle | Excluded | P1 |

### Demo에서 의도적으로 필수로 만들지 않는 것

Demo는 production-grade authentication/authorization, production DB lifecycle, complete retry/recovery, concurrency/CAS coverage, generic multi-room scaling, production deployment architecture, observability, security hardening, 모든 Constraint type, 범용 relaxation solver, complete P0 smart-contract lifecycle, production-grade receipt cryptographic protocol, `EMPTY` input handling, Merkle Input Set, ZK Proof, MPC, decentralized governance, local LLM, 실제 enterprise integration을 필수로 요구하지 않는다. 이는 삭제가 아니다. 각 항목은 기존 문서가 정한 대로 P0 또는 P1/P2 범위에 남는다.

## 6. Blockchain and commitment scope

### Required Demo integrity path

After a participant confirms a private input, create a minimal commitment from a canonical representation plus a fresh random salt:

```text
canonical private constraint + random salt → Keccak-256 → commitment hash
```

The receipt must show a decision identifier, the participant’s commitment/input evidence, final decision, integrity verification status, and a working `VERIFY` action. The verification action must recompute/compare the actual values it claims to verify.

### Preferred real-chain path

When feasible in the 3~4 day window, write at least one real EVM testnet record: a Condition Commitment **or** Final Decision Commitment. Receipt then shows the real `transaction_hash`, `contract_address`, `commitment_hash`, network and explorer/public verification link, and `VERIFY` compares against the public record.

### Honest fallback

If the real-chain path risks the representative demo, use local verification evidence or an explicitly simulated record only. Its UI must say `Demo local verification` or `Simulated — not on-chain`; it must never label it on-chain verified or present a fake transaction hash/explorer result. Full P0 `commitCondition`, all participant commitments, `ConstraintVersion` activation/retry states, frozen `participant_inputs`, `input_set_root`, finalization and single-transaction `supersedeCondition` remain P0 requirements, not Demo claims.

## 7. Demo completion criteria

The Pre-Screening Demo is complete only when all of the following can be demonstrated repeatedly.

1. Four participants exist in one Demo Decision Room.
2. Each can submit a private constraint.
3. AI structures at least one natural-language constraint.
4. The user reviews and approves that interpretation.
5. The first Engine run actually calculates `NO FEASIBLE SOLUTION`.
6. Conflict analysis identifies the representative relaxation target, and the selected Engine path produces the fixture-validated relaxation proposal.
7. Only the target participant receives the detailed proposal.
8. That user can choose `ACCEPT`.
9. The accepted input triggers a second real Engine calculation.
10. That calculation produces a feasible final decision.
11. A Participant Receipt can be opened.
12. Commitment or decision-integrity verification is demonstrable.
13. No other participant’s raw private constraint is exposed anywhere in the demo.
14. The full happy path can be reset and rerun reliably during a presentation.

### Engine cutline 운영 criterion

14개의 Demo Success Criteria는 그대로 유지한다. 별도로 Day 2 PM checkpoint에서 Decision/Negotiation path를 하나로 고정한다. generalized numeric minimum-relaxation search가 안정적이면 이를 사용하고, 안정화되지 않으면 아래 Demo representative relaxation fallback으로 전환한다. 이 운영 criterion은 P0 Decision Engine 계약을 변경하는 것이 아니라 3~4일 Demo 일정의 구현 위험을 제한하는 기준이다.

## 8. 3–4 day implementation schedule

### Decision Engine / Minimum Relaxation Cutline

Day 2의 가장 큰 구현 위험은 generalized conflict detection 및 generalized numeric minimum-relaxation search가 제한 시간 안에 안정화되지 않는 것이다. 따라서 **Day 2 저녁**을 명시적 Engine / Relaxation cutline으로 둔다. 단 fallback cutline의 대상은 generalized minimum-relaxation optimization뿐이며, conflict detection은 실제 constraint evaluation 결과에서 계속 도출한다. Day 3에는 어느 path를 쓸지 다시 열어 두지 않는다.

#### 정상 Engine path

우선 실제 deterministic logic으로 다음을 구현한다.

- candidate별 Hard Constraint filtering
- Soft preference scoring
- `FEASIBLE` / `NO FEASIBLE SOLUTION` 판정
- constraint evaluation 결과에 근거한 conflict detection
- numeric minimum-relaxation search
- `ACCEPT` 이후 변경 constraint를 적용한 recalculation
- deterministic final selection

대표 Demo fixture에서는 아래 결과가 실제 계산되어야 한다.

```text
initial constraints → NO FEASIBLE SOLUTION
minimum relaxation search → A.max_price 15000 → 17000
A ACCEPT → recalculation → FEASIBLE → deterministic final decision
```

#### Day 2 PM fallback Engine path

Day 2 저녁까지 generalized numeric minimum-relaxation search가 안정적으로 동작하지 않으면, Demo 범위를 확장하거나 Day 3까지 solver 작업을 끌고 가지 않는다. 대신 Demo 전용 fallback으로 전환한다. fallback은 representative `max_price` constraint에 한해 fixture로 사전 검증된 **Demo representative relaxation rule** proposal을 사용한다.

```text
A.max_price: 15000 → 17000
```

고정 가능한 것은 이 `17000` relaxation candidate/proposal뿐이다. `NO FEASIBLE SOLUTION`, `FEASIBLE`, `Final Decision`, selected candidate 전체를 하드코딩해서는 안 된다. fallback에서도 모든 candidate의 hard constraint를 실제 평가하고, feasible candidate가 0개인지 확인하며, 후보를 제거한 constraint evaluation을 추적하고, Demo 대상 numeric constraint를 relaxation candidate로 식별한다. 다른 participant constraint를 임의로 변경하지 않는다.

UI, 문서, 코드에서는 fallback을 general-purpose minimum relaxation solver로 표현하지 않고 **Demo representative relaxation rule** 또는 동등하게 명확한 명칭으로 표시한다.

### Day 1 QR/session cutline

QR 기반 join은 시연의 편의 기능이며 HUSH의 핵심 invariant가 아니다. **Day 1 오후**까지 실제 QR join과 participant session이 안정적으로 동작하지 않으면 QR 기반 동적 참가 구현을 중단한다. 이후 canonical demo는 사전 정의된 4개 demo participant session(`A`/`B`/`C`/`D`)으로 실행한다.

이 cutline은 private/shared 경계를 낮추지 않는다. 어느 방식을 택하든 participant별 private view와 shared view를 분리하고, 각 participant가 실제 private constraint를 입력하며, AI confirmation부터 commitment, decision, private negotiation, user approval, receipt/verification까지의 전체 Demo flow를 유지한다.

### Demo Dataset Fixture Freeze

Candidate Dataset은 별도 versioned Demo fixture로 관리한다. **늦어도 Day 2 오전까지** 다음 fixture-level scenario validation을 자동화하거나 같은 고정 입력으로 반복 실행 가능한 scenario check로 통과시킨 뒤 fixture를 freeze한다. 이는 dataset의 수학적/시나리오 관계를 검증하는 단계이며, generalized numeric minimum-relaxation search가 그 proposal을 안정적으로 찾아내는지의 구현 검증은 Day 2 PM Engine / Relaxation Cutline에서 별도로 한다.

1. initial constraints가 `NO FEASIBLE SOLUTION`을 산출한다.
2. A의 `max_price=15000` 상태에서는 feasible final candidate가 없다.
3. fixture-level scenario validation이 `A.max_price: 15000 → 17000`이 representative minimum relaxation임을 확인한다. 즉 `17000` 적용 후 feasible candidate가 존재하고, 그보다 작은 허용 범위에서는 feasible하지 않다.
4. 다른 participant의 `HARD` constraint 변경은 필요하지 않다.
5. A가 `ACCEPT`한 뒤 최소 하나 이상의 feasible candidate가 생성된다.
6. final selection은 deterministic하고, 동일 입력의 반복 실행은 동일 결과를 산출한다.

Freeze 이후 Demo 결과에 영향을 줄 수 있는 candidate field를 UI 편의만을 위해 임의 변경하지 않는다. 변경이 필요하면 위 scenario check를 다시 통과시키고, fixture version을 다시 freeze한다.

| Day / checkpoint | Deliverable and exit check |
|---|---|
| Day 1 — Core UI / Room / Input / AI | Demo project skeleton, Decision Room, private/shared UI separation, private input, AI structuring과 direct structured fallback을 만든다. **[CHECKPOINT]** 오후에 QR join/session의 안정성을 판단하고, 실패 시 즉시 A/B/C/D deterministic session으로 고정한다. |
| Day 1 — [PARALLEL] Blockchain infrastructure | EVM testnet 결정, demo wallet 준비, faucet 확보, RPC 연결 확인, 최소 contract skeleton 준비, deployment rehearsal, Explorer에서 transaction 조회를 시작한다. Day 1 종료 전에는 최소 한 번의 RPC·Explorer 경로를 확인한다. |
| Day 2 AM — Decision / Conflict / Dataset Fixture Freeze | Decision Engine과 conflict evaluation을 구현한다: deterministic hard filtering, soft scoring, feasibility 판정, constraint-evaluation 기반 conflict detection. **[MILESTONE] Dataset Fixture Freeze:** 위 fixture-level scenario validation을 통과시키고 fixture를 freeze한다. 이는 initial infeasible, `15000 → 17000` 뒤 feasible, smaller bound infeasible, deterministic final result라는 fixture 관계를 검증하며 generalized search 구현 성공을 의미하지 않는다. |
| Day 2 PM — generalized relaxation / Negotiation / Recalculation | generalized numeric minimum-relaxation search, private negotiation, working `ACCEPT`/`KEEP`, approved input 기반 recalculation과 final result를 연결한다. **[CHECKPOINT] Engine / Relaxation Cutline:** generalized search가 안정적이면 유지하고, 실패하면 representative `max_price` Demo representative relaxation rule fallback으로 전환한다. **[PARALLEL]** 최소 contract deployment rehearsal과 testnet record path를 계속 검증한다. |
| Day 3 — fixed Engine path / E2E and verification integration | Day 2 PM에 이미 결정한 Engine path를 사용해 canonical+salt commitment hashing, blockchain path의 Demo flow/Receipt/`VERIFY` 통합, full E2E 및 evidence capture를 완료한다. Day 3에는 generalized relaxation solver를 다시 확장하지 않고 Blockchain / Receipt / VERIFY integration에 집중한다. path가 불안정하면 polish 전에 명확히 labelled local verification으로 전환한다. |
| Day 4 — Feature freeze / stabilization | feature freeze, 대표 path error handling, deterministic reset verification, rehearsal, explorer/RPC fallback validation, recording/screenshots, final stabilization을 수행한다. |

Parallel work should preserve the interfaces above: one owner can stabilize the dataset/Engine fixture while another connects private/shared UI and another starts and verifies the blockchain infrastructure from Day 1. No work item may replace user confirmation with an AI action or loosen the shared-data boundary.

## 9. Demo risks and mitigations

### Demo risk escape routes

| Escape route | Cutline / trigger | Fallback and required boundary |
|---|---|---|
| QR/session | Day 1 PM cutline | predefined A/B/C/D sessions로 전환한다. participant-private/shared view 분리와 실제 private input flow는 유지한다. |
| Blockchain infrastructure | Day 1부터 병렬 검증 | live chain이 불안정하면 honest local/simulated verification으로 전환한다. UI는 `Demo local verification` 또는 `Simulated — not on-chain`으로 명시한다. |
| Dataset | Day 2 AM Dataset Fixture Freeze | 결과 영향 변경 시 scenario validation을 재실행한 뒤 version을 re-freeze한다. |
| Generalized Minimum Relaxation | Day 2 PM Engine / Relaxation Cutline | generalized search가 불안정하면 representative `max_price`의 **Demo representative relaxation rule** proposal fallback으로 전환한다. |

어느 escape route에서도 HUSH의 핵심 invariant는 제거하지 않는다. private raw constraint는 비공개이고, AI는 decision authority가 아니며, 사용자가 relaxation을 직접 `ACCEPT`/`KEEP`한다. hard filtering과 feasibility, `ACCEPT` 이후 recalculation, final decision은 실제 deterministic calculation으로 유지한다. verification 상태는 실제 구현보다 과장하지 않는다.

| Risk | Mitigation / presentation fallback |
|---|---|
| External LLM latency or malformed response | Preserve draft and provide a direct structured-input fallback; do not block the canonical flow. |
| QR join/session instability | Apply the Day 1 cutline and use deterministic A/B/C/D sessions without changing private/shared views or the rest of the flow. |
| EVM RPC, faucet, explorer indexing, or testnet instability | Start testnet/wallet/faucet/RPC/contract/explorer rehearsal on Day 1; prefer a confirmed record early; capture evidence; fall back only to clearly labelled local/simulated verification. |
| Dataset edit accidentally makes first run feasible or relaxation non-minimal | Freeze the fixture by Day 2 AM only after all scenario checks pass; rerun checks and re-freeze after every result-affecting change. |
| Generalized minimum-relaxation search is not stable by Day 2 PM | Apply the Engine / Relaxation Cutline: freeze the Demo path with the fixture-validated `A.max_price: 15000 → 17000` Demo representative relaxation rule; retain actual hard filtering, feasibility, conflict evaluation, approval-driven recalculation, and deterministic selection. |
| Shared UI leaks private data through status/debug views | Use a safe shared projection and rehearse all participant screens; show only generic conflict status. |
| Demo state cannot be repeated | Provide a reset to the same fixed room, inputs, salts/evidence policy, and candidate dataset. |

## 10. P0 preservation statement

**기존 P0 canonical contract 변경 없음.** 이 문서는 Stage A 구현의 범위를 명시할 뿐 `ConstraintVersion` lifecycle, Commitment lifecycle, `ParticipantInput`/`participant_inputs[]`, `EMPTY` input, `input_set_leaf`, `input_set_root`, DecisionRun freeze, single-transaction `supersedeCondition`, ParticipantReceipt, AI boundary, deterministic Engine authority, P0 privacy boundary, 또는 P0 independent verification을 수정·삭제·완화하지 않는다.
