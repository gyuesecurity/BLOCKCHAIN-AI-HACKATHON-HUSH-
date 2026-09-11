# HUSH

## 서로의 비밀을 밝히지 않고 합의하는 AI 협상 시스템

### Privacy-Preserving Conflict Resolution & Independent Verification

------------------------------------------------------------------------

## 1. 프로젝트 개요

-   **프로젝트명:** HUSH
-   **참가 트랙:** Track 03. Web3 기반 사회문제 해결
-   **개발 기간:** 7주
-   **팀 구성:** 4인
-   **핵심 키워드:** Minimum Necessary Disclosure, Private Negotiation,
    User Control, Independent Verification, Blockchain Commitment,
    Participant Receipt, Optional ZK Proof

### 한 줄 소개

**HUSH는 개인의 민감한 사유를 필요 이상 공개하지 않고 집단 합의를
만들며, AI가 최소한의 양보를 비공개로 제안하고, 참여자가 의사결정
운영자를 신뢰하지 않아도 자신이 승인한 조건이 어떤 입력과 어떤 규칙을
통해 최종 결정에 연결되었는지 공개된 증거를 통해 독립적으로 검증할 수
있게 하는 AI·Web3 협상 시스템이다.**

### 핵심 슬로건

> **비밀은 지키고, 반영됐다는 사실은 증명한다.**

### HUSH의 최종 핵심 메시지

> **"결정을 내린 사람과 그 결정이 정당했다고 증명하는 사람이 같아서는 안
> 됩니다."**

### HUSH가 던지는 질문

> **"집단의 결정에 내 사정을 반영받기 위해, 왜 그 사정까지 설명해야
> 하는가?"**

> **"의사결정을 운영하는 사람이 결과와 검증 기록까지 모두 통제한다면,
> 참여자는 자신의 조건이 실제로 반영되었는지 어떻게 확인할 수 있는가?"**

HUSH는 단순히 비밀 조건으로 추천 결과를 만드는 서비스가 아니다. 핵심은
두 가지다.

1.  **비공개 조건끼리 충돌해 그대로는 합의가 불가능한 순간**을 어떻게
    푸는가
2.  그렇게 만들어진 합의를, **운영자의 말을 그대로 믿지 않고도**
    참여자가 어떻게 검증하는가

------------------------------------------------------------------------

# 2. 문제 정의

여러 사람이 함께 장소, 일정, 여행, 행사, 역할 등을 결정할 때 각자는 서로
다른 제약을 가진다. 문제는 어떤 제약은 결과에 반드시 반영되어야 하지만,
그 이유까지 타인에게 설명하고 싶지는 않다는 점이다.

예를 들어 네 명이 저녁 장소를 정한다고 가정한다.

-   A는 개인적인 경제 사정 때문에 **15,000원 이하**여야 한다.
-   B는 개인적인 이유로 **특정 음식을 먹을 수 없다.**
-   C는 **접근 가능한 장소**가 필요하지만 그 이유를 설명할 필요는 없다.
-   D는 돌봄 또는 개인 일정 때문에 **21시 이전 귀가**가 필요하다.

기존 대화에서는 결국 "왜 거기는 안 돼?", "왜 꼭 그 시간이어야 해?",
"조금만 더 쓰면 안 돼?" 같은 질문이 생긴다. 조건을 존중받으려면 사정을
설명해야 하고, 설명하지 않으면 단순한 취향이나 고집으로 받아들여질 수
있다.

## HUSH가 정의하는 사회문제

> **개인의 민감한 사정을 공개해야만 그 사람의 제약이 충분히 존중받을 수
> 있는 집단 의사결정 구조**

HUSH는 이를 두 가지 권리의 문제로 본다.

### 설명하지 않을 권리

필요 이상의 개인 사정을 타인에게 공개하지 않을 수 있어야 한다.

### 배제되지 않을 권리

이유를 공개하지 않았다는 이유로 중요한 제약이 의사결정에서 무시되어서는
안 된다.

------------------------------------------------------------------------

# 3. 진짜 어려운 순간 --- Conflict

모든 조건을 만족하는 선택지가 있으면 문제는 쉽다.

``` text
Private Constraints → Decision Engine → Feasible Result
```

진짜 어려운 순간은 다음이다.

``` text
Private Constraints → Decision Engine → NO FEASIBLE SOLUTION
```

일반적인 협상에서는 이 순간 서로의 조건을 공개하면서 조정한다. 그러나
민감한 조건이라면 이 과정에서 프라이버시가 깨질 수 있다.

> **Privacy-Preserving Constraint Satisfaction을 넘어,
> Privacy-Preserving Conflict Resolution을 구현한다.**

즉, **비밀을 숨긴 채 계산하는 것뿐 아니라 비밀끼리 충돌했을 때도 비밀을
폭로하지 않고 합의를 찾아가는 것**이 HUSH의 첫 번째 핵심이다.

그리고 그렇게 만들어진 합의가 **정말로 신뢰할 수 있는지 참여자가 직접
확인할 수 있는 것**이 HUSH의 두 번째 핵심이다.

------------------------------------------------------------------------

# 4. HUSH의 신뢰 구조 --- 3축

HUSH는 기능을 나열하는 대신, 다음 세 가지 축으로 설명한다. AI·Decision
Engine·Blockchain은 모두 이 세 가지 목적을 구현하기 위한 수단일 뿐이다.

``` text
               HUSH

        Private Constraints
               │
               ▼
┌──────────────────────────────┐
│ ① PRIVATE NEGOTIATION        │
│                              │
│ Conflict Detection           │
│ Minimum Relaxation           │
│ Minimum Necessary Disclosure │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ ② USER CONTROL               │
│                              │
│ AI Proposal                  │
│ User Approval                │
│ Versioned Re-Commit          │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ ③ INDEPENDENT VERIFICATION   │
│                              │
│ Condition Commitment         │
│ Input Set Root               │
│ Engine Code Hash             │
│ Decision Commitment          │
│ Participant Receipt          │
│ Public Explorer Verification │
└──────────────────────────────┘
```

### ① Private Negotiation

> 비공개 조건이 충돌해도 필요한 정보만 사용해 최소한의 양보를 찾는다.

### ② User Control

> AI가 조건을 마음대로 바꾸지 않고, 모든 양보는 당사자가 직접 승인한다.

### ③ Independent Verification

> 운영자나 HUSH 앱의 말을 믿는 대신, 어떤 조건과 어떤 코드 버전으로
> 결정이 만들어졌는지 참여자가 공개된 증거로 직접 검증한다.

발표에서는 Participant Receipt, Explorer 검증, Engine Code Hash,
Immutable Contract를 각각 별도의 핵심 기능처럼 설명하지 않는다. 이
모두는 **③ Independent Verification**을 구현하기 위한 하위 기술이다.

------------------------------------------------------------------------

# 5. ① Private Negotiation

## 5.1 비공개 조건 입력

사용자는 자신의 스마트폰에서 자연어로 조건을 입력한다.

> "돈을 조금 아껴야 해서 2만원 넘는 곳은 부담스러운데, 다른 사람에게
> 이유까지 말하고 싶지는 않아. 고기는 좋아."

AI는 다음처럼 구조화한다.

``` json
{
  "hard_constraints": { "max_price": 20000 },
  "soft_preferences": { "category": "meat" },
  "visibility": "private"
}
```

구조화 결과는 자동 적용되지 않는다.

``` text
AI INTERPRETATION
필수 조건 ✓ 20,000원 이하
선호 조건 ✓ 고기 선호
공개 범위 🔒 PRIVATE
[수정] [확정]
```

**사용자가 직접 확정한 조건만 의사결정에 사용한다.**

## 5.2 Hard Constraint / Soft Preference

**Hard Constraint** --- 반드시 지켜야 하는 조건 (최대 가격, 특정 음식
제외, 접근 가능 여부, 최대 이동 시간, 종료 시간 등). 하나라도 만족하지
못하는 후보는 선택할 수 없다.

**Soft Preference** --- 가능하면 만족하면 좋은 선호 (고기 선호, 조용한
장소, 이동거리 최소화 등).

``` text
Candidate Dataset → Hard Constraint Filtering → Feasible Candidates
→ Soft Preference Scoring → Best Candidate
```

실제 조건 충족 여부는 LLM이 임의로 판단하지 않는다. **Deterministic
Decision Engine이 동일 입력에 대해 재현 가능한 방식으로 계산한다.**

## 5.3 Conflict Detection

모든 Hard Constraint를 만족하는 후보가 없으면 HUSH는 단순히 "추천 결과
없음"으로 끝나지 않는다. Decision Engine은 어떤 조건 조합 때문에 해가
존재하지 않는지 내부적으로 식별한다.

``` text
RESULT: NO FEASIBLE SOLUTION
Conflict Set (internal): C1 + C4 + C7 → UNSAT
```

그러나 `C1`, `C4`, `C7`의 내용과 소유자를 다른 참가자에게 그대로
공개하지 않는다.

## 5.4 Minimum Relaxation

HUSH는 가능한 여러 조건 변경 시나리오를 비교해 **가장 적은 양보로 합의를
만들 수 있는 후보**를 계산한다.

HUSH가 지향하는 우선순위:

1.  Hard Constraint 위반 최소화
2.  민감정보 공개 최소화
3.  사용자 양보량 최소화
4.  전체 Soft Preference 만족도 최대화

``` text
minimize: constraint_violation + privacy_disclosure + relaxation_cost
maximize: group_preference_score
```

MVP에서는 모든 제약을 하나의 복잡한 수학 모델로 일반화하기보다,
**가격·거리·시간처럼 완화량을 정량화할 수 있는 조건부터 지원**한다.

## 5.5 Minimum Necessary Disclosure

> "누구의 비밀도 폭로하지 않는다"는 표현은 완전한 무노출(Zero
> Disclosure)로 오해될 수 있어 **Minimum Necessary Disclosure**로
> 통일한다.

HUSH가 실제로 보장하는 것:

> **조건의 원문과 구체적인 개인 사유를 다른 참가자에게 직접 공개하지
> 않고, 합의를 위해 필요한 정보 노출을 최소화한다.**

전체 참가자에게는 다음 수준까지만 보여준다.

``` text
PRIVATE CONFLICT DETECTED
A minimal adjustment from 1 participant can create a feasible solution.
Participant identity: HIDDEN
Private constraint: HIDDEN
```

공개하지 않는 것: 누구의 조건인지, 어떤 종류의 민감 조건인지, 실제 값이
얼마인지, 왜 그 조건이 필요한지. 필요한 정보는 해당 사용자에게만
전달한다.

------------------------------------------------------------------------

# 6. ② User Control

## 6.1 AI Private Negotiation

Minimum Relaxation 결과를 바탕으로 AI가 해당 사용자에게만 협상안을
설명한다.

``` text
PRIVATE NEGOTIATION
현재 조건: 최대 예산 15,000원
17,000원까지 허용할 경우 모든 참가자의 필수 조건을 만족하는
3개의 선택지가 생성됩니다.
[기존 조건 유지] [17,000원까지 허용]
```

AI는 **제안만 할 수 있다.**

-   거절 시 → `RELAXATION REJECTED — Original constraint preserved.`
-   승인 시 → `RELAXATION APPROVED — Condition v2 will be created.`

즉, HUSH는 **AI가 사람의 제약을 마음대로 완화하는 시스템이 아니라,
사람에게 필요한 최소 변경안을 비공개로 제시하고 최종 결정권은 사용자에게
남기는 시스템**이다.

## 6.2 AI의 역할과 한계

**AI가 하는 것:** ① Constraint Parsing(자연어→조건 추출) ② Constraint
Structuring(정형화) ③ Conflict Explanation(민감정보 노출 없는 설명 생성)
④ Private Negotiation(완화 시나리오 설명)

**AI가 하지 않는 것:** 사용자 승인 없는 조건 변경, 민감 조건을 다른
참가자에게 공개, Hard Constraint 임의 무시, 최종 결과 임의 확정,
사용자를 대신한 Blockchain 승인

> **AI는 협상을 돕지만 권한자는 아니다.**

------------------------------------------------------------------------

# 7. ③ Independent Verification

## 7.1 왜 블록체인인가 --- 무결성 저장이 아니라 독립적 검증

Condition Commitment, Versioned Re-Commit, Decision Commitment만으로는
"서버 DB에 hash-chain이나 서명 로그를 저장해도 되지 않느냐"는 질문을
피하기 어렵다. HUSH는 블록체인의 필요성을 다음 질문에서 출발시킨다.

> **의사결정을 수행하는 운영자가 서버와 검증 기록까지 모두 통제한다면,
> 참여자는 운영자를 신뢰하지 않고 자신의 승인 조건이 실제 최종 결정에
> 포함되었는지 어떻게 확인할 수 있는가?**

따라서 HUSH에서 블록체인은 **의사결정 운영자와 독립된 공용 검증
레이어**로 정의한다.

> **HUSH가 블록체인을 사용하는 이유는 DB보다 Hash를 잘 저장하기 위해서가
> 아니라, 의사결정을 운영하는 기관이 검증 기록까지 독점하지 못하도록
> 하기 위해서다.**

## 7.2 Condition Commitment

민감한 조건 자체는 온체인에 올리지 않는다.

``` text
Canonical Condition + Random Salt → Keccak-256 → Condition Commitment
```

온체인에는 최소 정보만 기록한다: Decision ID / Participant Pseudonym /
Condition Commitment / Condition Version / Timestamp / Status. 실제
조건과 Salt는 Off-chain에 저장한다.

## 7.3 Versioned Re-Commit

Private Negotiation으로 조건이 바뀌더라도 기존 기록을 덮어쓰지 않는다.

``` text
Condition v1: max_price ≤ 15,000  Commitment 0x72AF...  SUPERSEDED
        ↓ USER APPROVED RELAXATION
Condition v2: max_price ≤ 17,000  Commitment 0x91BC...  ACTIVE
```

이를 통해 최초 승인 조건, 변경 전후 버전, 사용자 승인 이후 변경 여부,
최종 결정에 사용된 버전, 사후 임의 변경 여부를 검증할 수 있다.

## 7.4 Decision Commitment (+ Engine Code Hash)

최종 결과만 Hash로 저장하지 않고, **어떤 입력 집합·어떤 코드로 결과가
만들어졌는지**까지 연결한다.

``` text
Input Set Root
+ Candidate Dataset Hash
+ Decision Engine Version
+ Decision Engine Code Hash
+ Final Result Hash
        ↓
Decision Commitment
```

Decision Engine은 GitHub에 오픈소스로 공개하고, 최종 Decision에 사용된
Engine Version/Code Hash를 온체인 기록과 연결한다. 이를 통해 검증자는
다음을 확인할 수 있다.

``` text
✓ 어떤 조건 집합이 사용됐는가
✓ 어떤 후보 데이터가 사용됐는가
✓ 어떤 Decision Engine 버전/코드가 사용됐는가
✓ 어떤 결과가 기록됐는가
✓ 필요할 경우 동일 버전·동일 입력으로 결과 재현 가능
```

단, 표현은 정확히 유지한다: **Blockchain이 Decision Engine의 계산
정확성을 자동으로 증명하는 것은 아니다.** MVP는 입력·코드 버전·결과의
provenance와 재현 가능성을 제공하며, 계산 자체의 암호학적 정확성 검증은
ZK 등 향후 확장 영역으로 둔다.

## 7.5 Participant Receipt

각 참여자가 자신이 승인한 조건과 최종 Decision의 연결 관계를 **HUSH 앱
밖에서도** 직접 검증할 수 있도록 한다. HUSH 앱의 `VERIFIED ✓` 표시를
그대로 믿는 구조가 아니라, 사용자가 원하면 공개 블록체인 데이터를 직접
조회해 동일한 검증을 스스로 수행할 수 있어야 한다.

``` text
HUSH PARTICIPANT RECEIPT

Decision              2026 University Workshop
My Condition Version  v2
Condition Commitment  0x91BC...
Transaction Hash      0x4a1c...
Input Set Root        0x7f0d...
Final Decision Hash   0xe3b2...
Network                HUSH Testnet (EVM)
Contract Address       0x2C1a...

Included in Final Input Set   ✓
On-chain Verification         VERIFIED ✓
```

## 7.6 Public Explorer 검증 흐름

``` text
Participant Receipt
        ↓
Transaction Hash 확인
        ↓
Public Testnet Explorer
        ↓
Contract Address 확인 → Transaction 확인
        ↓
Commitment / Decision 값 비교
        ↓
Open-source Engine 확인 → Engine Code Hash 비교
        ↓
MATCH ✓
```

핵심 메시지: **HUSH의 검증 결과를 믿는 것이 아니라, HUSH가 제시한 증거를
누구나 독립적으로 검증할 수 있다.**

## 7.7 HUSH 플랫폼 자체에 대한 신뢰 경계

`Independent Verification`은 의사결정 운영자로부터의 독립성은
확보하지만, HUSH 플랫폼 자체가 완전히 trustless한 것은 아니다. 다음
가능성은 MVP에서 완전히 제거되지 않는다.

-   HUSH가 처음부터 악의적인 Decision Engine을 배포하는 경우
-   HUSH가 검증과 다른 Engine 코드를 실제로 실행하는 경우
-   Smart Contract가 업그레이드 가능하다면 이후 로직이 변경되는 경우
-   HUSH의 Frontend가 잘못된 정보를 표시하는 경우

이를 명확히 인정하고 신뢰 경계를 다음과 같이 정의한다.

> **HUSH MVP의 Independent Verification은 의사결정 운영자(대학·기업·행사
> 운영자)로부터의 독립성을 우선 목표로 한다. HUSH 플랫폼 자체에 대한
> 신뢰는 Decision Engine과 Smart Contract의 소스코드 공개, Code Hash
> 검증, 업그레이드 불가능한 MVP Contract를 통해 최소화하며, 완전한
> 탈중앙 신뢰 구조는 향후 확장 과제로 둔다.**

``` text
[운영자 신뢰]
대학 / 기업 / 행사 운영자 → 신뢰하지 않아도 검증 가능 → Public Blockchain → Participant Verification

[HUSH 자체 신뢰]
HUSH Engine + HUSH Smart Contract → Open Source / Code Hash / Immutable MVP Contract → 신뢰 최소화

완전한 Trustless Governance → MVP 범위 밖 (Future Work)
```

Smart Contract는 "나중에 HUSH가 로직을 바꾸면 어떻게 하는가"라는 질문을
줄이기 위해 Proxy/Upgradeable 구조를 사용하지 않고 **단순한 immutable
deployment**로 설계한다.

> "시연에 사용되는 Contract는 배포 이후 HUSH가 임의로 로직을 변경할 수
> 없는 구조로 고정하고, 실제 배포 주소와 소스코드를 공개합니다."

## 7.8 블록체인이 보장하는 것 / 보장하지 않는 것

**MVP에서 보장하려는 것** - 사용자가 어떤 조건 버전을 승인했는가 -
승인된 조건이 Final Input Set에 포함됐는가 - 어떤 Candidate Dataset을
사용했는가 - 어떤 Decision Engine 버전/코드를 사용했는가 - 어떤 Final
Result가 기록됐는가 - 해당 기록이 사후 변경되었는가

**MVP가 완전히 보장하지 않는 것** - LLM의 자연어 해석이 항상 정확한가 -
사용자가 입력한 개인 사정이 현실에서 사실인가 - 소규모 그룹에서 조건
소유자를 절대 추론할 수 없는가 - Decision Engine의 모든 계산이
암호학적으로 정확한가 (→ 공개된 Engine을 통한 재현 가능성으로 보완, ZK는
P1 확장) - 외부 시스템이나 모델 제공자에게 이미 전달·복제된 민감정보를
사후에 완전히 회수할 수 있는가

즉: **Blockchain = AI의 정답 증명이 아니라, 운영자·HUSH 자체로부터
최소화된 신뢰를 전제로 한 Provenance & Verification Layer다.**

------------------------------------------------------------------------

# 8. Privacy Limitations --- 먼저 인정하는 한계

HUSH가 완전한 프라이버시 보장을 주장하지 않도록, 다음 두 가지 한계를
명시한다.

### 외부 LLM API 문제

MVP는 외부 LLM API로 자연어 조건을 구조화하므로, 민감한 원문이 모델
제공자에게 처리될 수 있다. 따라서 MVP의 프라이버시 목표는 우선
**참가자와 운영자 사이의 불필요한 정보 노출 최소화**로 한정한다. 향후
Local LLM, On-device Model, Confidential Computing을 통한 확장을
지향한다.

### 소규모 그룹의 추론 가능성

4명과 같은 작은 집단에서는 "1명의 조건 완화가 필요하다"는 정보만으로도
주변 정황을 통해 해당 사용자를 추론할 가능성이 있다. 따라서 HUSH는
완전한 익명성을 보장한다고 주장하지 않는다.

> **소규모 그룹에서는 주변 정보에 따른 추론 가능성이 존재하지만, 조건
> 원문과 구체적인 개인 사유의 직접 공개는 최소화한다.**

------------------------------------------------------------------------

# 9. Zero-Knowledge Proof --- 완전한 Optional P1

Commitment는 입력과 결과의 무결성을 연결하지만, **비공개 조건이 실제
계산에서 만족됐다는 사실 자체를 암호학적으로 증명하지는 않는다.** 이를
보완하기 위해 P1에서 단순한 수치형 Hard Constraint 한 종류(가격 상한)에
ZK Proof를 적용한다.

``` text
PRIVATE   max_budget = 17,000
PUBLIC    selected_price = 16,000
증명 명제  selected_price ≤ private_max_budget
```

``` text
Constraint Satisfied: YES
Proof: VALID ✓
```

**구현 원칙:** ZK 없이도 HUSH의 핵심 스토리와 데모가 완결되도록
구성한다. ZK는 3축 흐름이 완성된 이후에만 진행하는 P1 기능이며, **Week
5까지 P0가 안정적이지 않으면 ZK 구현을 제외한다.**

------------------------------------------------------------------------

# 10. 대표 MVP 시나리오와 실제 사업 타깃의 분리

친구 4명의 저녁 장소 결정은 HUSH를 직관적으로 설명하기 위한 **축소
데모**로 유지한다. 다만 이 상황 자체를 HUSH의 주요 사업 문제로 제시하면
블록체인의 필요성이 약해진다. 실제 적용 대상은 **조건 제출자와 의사결정
운영자가 서로 다른 환경**이다.

``` text
친구 4명의 저녁 약속  = 기술을 이해시키기 위한 축소 데모
대학 · 기업 · 행사 운영자 ↔ 참가자 = 실제 해결하려는 신뢰 문제
```

------------------------------------------------------------------------

# 11. 최종 시연 시나리오

## STEP 1 --- Decision Room

QR 코드로 4명이 각자 스마트폰에서 참가한다. `4 / 4 CONNECTED`

## STEP 2 --- 비공개 조건 제출

A(가격), B(음식), C(접근성), D(시간) 각자 조건을 자연어로 제출한다. 공용
화면: `PRIVATE CONDITIONS — A🔒 B🔒 C🔒 D🔒 — Raw Conditions Shared: NO`

## STEP 3 --- AI 구조화 및 사용자 승인

각자의 스마트폰에서 AI INTERPRETATION을 확인하고 `[확정]`. 4명 모두
확정.

## STEP 4 --- Blockchain Commitment

`4 / 4 COMMITTED`

## STEP 5 --- 첫 번째 계산

`❌ NO FEASIBLE SOLUTION`

## STEP 6 --- Conflict Analysis

공용 화면에는 대상자를 공개하지 않고
`Conflict detected. Raw private conditions shared: NO`만 표시.
내부적으로 여러 완화 시나리오를 계산한다.

## STEP 7 --- Minimum Relaxation

`MINIMUM RELAXATION FOUND — Required adjustments: 1 — Feasible options after approval: 3`

## STEP 8 --- 해당 사용자에게만 협상

A의 스마트폰에만 `15,000원 → 17,000원 제안`. A가 `[ACCEPT]`.

## STEP 9 --- Versioned Re-Commit

`v1 → v2 — User Approval ✓ — New Commitment ✓ — Blockchain CONFIRMED`

## STEP 10 --- 최종 Decision

`샤브샤브 C — HARD CONSTRAINTS 4/4 ✓ — RAW PRIVATE CONDITIONS SHARED: NO — USER-APPROVED RELAXATIONS 1 — DECISION INTEGRITY VERIFIED ✓`

## STEP 11 --- Participant Receipt & Explorer 검증 (신규)

A의 스마트폰에서 Participant Receipt를 열어 Transaction Hash를 확인 →
Public Testnet Explorer로 이동 → Contract Address와 Transaction을 직접
조회 → Receipt의 Commitment 값과 비교 → `MATCH ✓`

**Fallback:** Explorer 인덱싱 지연/네트워크 장애 시, 사전 캡처한
Explorer 화면 또는 사전 녹화된 Verification 영상으로 동일 Transaction
Hash를 확인하는 백업 경로를 사용한다.

## STEP 12 --- Optional ZK Demo (P1)

`selected_price(16,000) ≤ private_max_budget — ZK PROOF VALID ✓`

## STEP 13 --- Tampering Attack

관리자 Demo Panel에서 Off-chain 데이터를 변경 →
`❌ INVALID — COMMITMENT MISMATCH`. 복원 시 `✓ VERIFIED`.

------------------------------------------------------------------------

# 12. 최종 발표에서 보여줄 핵심 지표

``` text
HARD CONSTRAINTS              4 / 4 ✓
RAW PRIVATE CONDITIONS SHARED    NO
PRIVATE REASONS SHARED            NO
USER-APPROVED RELAXATIONS          1
DECISION INTEGRITY           VERIFIED ✓
```

> 모두의 필수 조건을 지켰다. 누구의 비밀도 필요 이상 폭로하지 않았다.
> 필요한 양보는 당사자가 직접 승인했다. 최종 합의 기록은 누구나
> 독립적으로 검증할 수 있다.

------------------------------------------------------------------------

# 13. 시스템 아키텍처

``` text
┌──────────────────────────────┐
│         Participants A B C D │
└──────────────┬───────────────┘
               │ Private Input
               ▼
┌──────────────────────────────┐
│     AI Constraint Parser     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│       User Confirmation      │
└──────────────┬───────────────┘
        ┌──────┴────────┐
        ▼               ▼
Private Constraint Store (Off-chain)    Condition Commitment → Blockchain
                                             │
                                             ▼
┌──────────────────────────────┐
│     Deterministic Engine     │
│ Hard Filter / Soft Optimize  │  (Open Source, Code Hash)
└──────────────┬───────────────┘
        ┌──────┴───────┐
     Feasible        Conflict
        │              ▼
        │     Conflict Analyzer → Minimum Relaxation/Disclosure
        │              ▼
        │     AI Private Negotiation → User Approval → Versioned Re-Commit
        └───────┬──────┘
                ▼
┌──────────────────────────────┐
│       Final Consensus        │
└──────────────┬───────────────┘
               ▼
Decision Commitment (+ Engine Code Hash) → Blockchain (Immutable Contract)
               ▼
Participant Receipt → Public Explorer → Independent Verify
```

------------------------------------------------------------------------

# 14. 기술 스택

**Frontend:** Next.js, React, Tailwind CSS, 모바일 참가 UI, QR 기반
Decision Room, Participant Receipt/Explorer 연동 화면

**Backend:** FastAPI, PostgreSQL, WebSocket 또는 polling, Private
Constraint Store (Off-chain)

**AI:** LLM API, Structured Output, Constraint Parser, Conflict
Explanation, Private Negotiation Message Generator

**Decision/Optimization:** Python, Deterministic Hard Constraint Filter,
Soft Preference Scoring, Conflict Set Detection, Minimum Relaxation
Search --- **GitHub 공개, Code Hash 생성**

**Blockchain:** Solidity, EVM Testnet, **Immutable(비-업그레이더블)
Decision Registry**, Versioned Condition Commitment, Input Set Root,
Decision Commitment(+Engine Code Hash), Public Explorer 연동

**Cryptography:** Keccak-256, Random Salt, Canonical JSON, Merkle Root
또는 deterministic set root

**P1 ZK:** 단순 range/inequality circuit ---
`selected_price ≤ private_max_budget`

------------------------------------------------------------------------

# 15. Smart Contract MVP

``` solidity
createDecision()
commitCondition()
supersedeCondition()
finalizeInputSet()
commitDecision()       // Input Set Root + Candidate Dataset Hash + Engine Code Hash + Result Hash
verifyDecisionRecord()
```

Smart Contract에는 민감한 조건 원문을 저장하지 않는다. **배포 이후
로직을 변경할 수 없는 immutable 구조**로 설계하고, 배포 주소와
소스코드를 공개한다.

------------------------------------------------------------------------

# 16. 7주 개발 계획

## Week 1 --- Core Model + UX Prototype

문제 시나리오 확정, Constraint Schema, Hard/Soft 모델, Decision Room,
모바일 Private Input, Candidate Dataset, Blockchain 데이터 모델. **완료
기준:** 4명이 Room에 참가하고 비공개 조건을 입력할 수 있다.

## Week 2 --- AI Constraint Parser

자연어→Structured Constraint, Hard/Soft 분류, 사용자 수정/확정,
Visibility, Parser 테스트. **완료 기준:** 자연어 입력부터 사용자
승인까지 완성.

## Week 3 --- Decision + Conflict Engine

Hard Constraint filtering, Soft scoring, Feasibility 판단, Conflict
detection, 완화 가능한 수치형 조건 정의. **완료 기준:**
`FEASIBLE / NO FEASIBLE SOLUTION`을 재현 가능하게 계산.

## Week 4 --- Blockchain Trust Layer (배포 리허설)

Condition Commitment, Smart Contract 개발, Version 관리, Input Set Root,
Decision Commitment 설계, **Participant Receipt 화면 및 Explorer 링크
연동**, Testnet **배포 리허설**(인터페이스 안정화 목적, 최종 확정 배포
아님). **완료 기준:** 사용자 승인 조건부터 결과까지 검증 가능한 기록
연결 + Receipt 화면 동작.

## Week 5 --- Minimum Relaxation + Private Negotiation

완화 시나리오 탐색, relaxation cost, 대상 사용자 비공개 라우팅, AI 협상
설명, 사용자 ACCEPT/KEEP, Versioned Re-Commit. **완료 기준:**
`NO SOLUTION → CONFLICT → PRIVATE NEGOTIATION → USER APPROVAL → NEW SOLUTION`
전체 흐름 완성. **체크포인트:** 이 시점까지 P0가 불안정하면 ZK(P1)는
제외한다.

## Week 6 --- Verification 강화 + 안정화

Commitment/Decision verification, Tampering Demo, Verification
Dashboard, Engine Code Hash 연동, Contract Interface Freeze, E2E
테스트를 진행한다. (P1) P0가 안정된 경우에만 가격 상한 ZK Proof 1종을
시도한다.

**완료 기준:** 정상 상태 `VERIFIED`, 변조 상태 `INVALID`, 대표 시나리오
반복 실행 성공.

### Week 6 말 \~ Week 7 초 --- Final Immutable Deployment

최종 리허설에 사용할 검증 대상을 한 번에 고정한다.

``` text
Decision Engine Final Git Commit
        ↓
Engine Code Hash 생성
        ↓
Smart Contract 최종 확정 배포
        ↓
Contract Address 고정
        ↓
Demo Dataset 고정
        ↓
Demo Transaction 생성
        ↓
Participant Receipt 고정
```

최종 배포 이후 Contract 로직 변경이 필요하면 기존 Contract를 수정하지
않고 새 Contract를 재배포하며, 관련 Receipt·Transaction·검증 데이터를
모두 다시 생성한다.

## Week 7 --- Freeze / 리허설 / 발표

Week 7에는 신규 기능을 개발하지 않는다. 전체 UI 통합 상태를 점검하고
예외 처리, UI 가독성 개선, 발표용 Dashboard, GitHub 정리, Architecture
Diagram, 반복 리허설과 백업 준비에 집중한다.

**최종 Freeze 대상** - Engine Git Commit - Engine Code Hash - Contract
Address - Demo Dataset - Demo Transaction Hash - Participant Receipt

**Explorer Live Demo 백업** - Explorer Transaction 화면 사전 캡처 -
Contract Address / Transaction Hash 별도 기록 - Participant Receipt와
On-chain 값 비교 화면 캡처 - Explorer Verification 사전 녹화 영상 - 전체
Demo Video 백업

> Engine Code Freeze 이후 코드가 변경되면 Code Hash와 관련 Demo
> Evidence를 모두 재생성한다.

**최종 목표:** 5분 내 전체 핵심 흐름을 실제 작동하는 화면으로 안정적으로
보여준다.

------------------------------------------------------------------------

# 17. 7주 구현 우선순위 (동결)

## P0 --- 반드시 구현 (더 이상 확장하지 않음)

``` text
Private Constraint Input → AI Structuring → User Confirmation → Condition Commitment
→ Decision Engine → Conflict Detection → Minimum Relaxation → Private Negotiation
→ User Approval → Versioned Re-Commit → Final Decision → Decision Commitment
→ Participant Receipt → Independent Verification
```

## P1 --- 가능하면 구현 (Week 5 P0 불안정 시 제외)

-   가격 조건 1종 ZK Proof
-   Merkle 기반 Input Set
-   사용자 서명 강화
-   협상 시나리오 비교 UI

## P2 --- 해커톤 이후 (Future Work)

-   완전한 탈중앙 Governance
-   범용 MPC
-   Local LLM / On-device 구현
-   모든 Constraint의 ZK 검증
-   복잡한 Smart Contract Governance
-   실제 기업 시스템 연동
-   완전한 익명성 프로토콜

## 팀 Scope Freeze 운영 규칙

문서상의 P0 동결이 실제 개발 중 기능 확장으로 무너지지 않도록 다음
규칙을 적용한다.

1.  현재 정의된 P0 목록 이후의 신규 기능 요청은 P0에 추가하지 않고
    P1/P2/Future Work로 분류한다.
2.  **발표 2주 전부터 신규 기능 구현을 금지한다.**
3.  발표 2주 전부터 허용되는 작업은 **P0 버그 수정, UI 가독성 개선,
    성능·안정화, 데모 리허설**로 제한한다.
4.  Engine Freeze 이후 코드가 변경되면 Engine Code Hash와 관련 Demo
    Evidence를 모두 다시 생성한다.
5.  Final Immutable Contract 배포 이후 로직 변경이 필요하면 새
    Contract를 재배포하고 Contract Address, Transaction, Receipt를 다시
    생성한다.
6.  P0가 Week 5 체크포인트까지 안정적이지 않으면 ZK를 포함한 모든 P1
    작업을 중단한다.

------------------------------------------------------------------------

# 18. 기존 기술과의 차별화 방향

HUSH는 "비공개 조건을 이용해 계산한다"는 개념 자체를 최초라고 주장하지
않는다. Privacy-Preserving Constraint Satisfaction과 분산 최적화는 기존
연구 영역이며, 이미 조건 원문 비공개나 최적화 자체는 잘 해결되어 있다.
HUSH가 집중하는 지점은 그 다음 단계다.

  ------------------------------------------------------------------------------------
  구분           일반 투표   일반 AI     Privacy-Preserving   HUSH
                             추천        Constraint           
                                         Computation          
  -------------- ----------- ----------- -------------------- ------------------------
  자연어 개인    제한적      가능        보통 정형 입력       AI 구조화
  조건                                                        

  조건 원문      제한적      운영자 의존 가능(핵심 강점)      가능
  비공개                                                      

  Hard/Soft 구분 제한적      모델 의존   가능                 Deterministic

  해가 없을 때   재투표      재추천      문제별 상이          Minimum
  충돌 처리                                                   Relaxation·Negotiation

  조건 소유자    어려움      보장 없음   주목적 아님          Private Negotiation
  비공개 협상                                                 

  사용자 승인    수동        서비스별    시스템별 상이        Versioned Re-Commit
  기반 변경                  상이                             

  운영자로부터   낮음        운영자 의존 시스템별 상이        Participant Receipt /
  독립된 검증                                                 Explorer

  비공개 조건    없음        없음        암호기술에 따라 가능 P1 ZK PoC
  만족 증명                                                   
  ------------------------------------------------------------------------------------

### HUSH의 차별화 문장

> **기존 privacy-preserving computation이 비밀을 숨긴 채 결과를 계산하는
> 것에 강점이 있다면, HUSH는 그 위에서 현실의 집단 의사결정에서 더
> 어려운 두 가지 순간 --- '비공개 조건끼리 충돌해 해가 없는 상황'과
> '운영자를 신뢰하지 않아도 되는 검증' --- 을 하나의 Decision
> Lifecycle로 연결한다.**

------------------------------------------------------------------------

# 19. Track 03 적합성

HUSH의 출발점은 기술이 아니라 다음 사회문제다.

> **개인의 민감한 사정을 설명하지 않으면 자신의 제약이 충분히 존중받기
> 어려운 문제**

대상 조건: 경제적 사정, 접근성 요구, 식이 제한, 돌봄 책임, 귀가·근무
시간, 개인 일정, 공개하기 어려운 생활 제약.

> **필요한 조건만 반영하고, 필요하지 않은 개인정보는 요구하지 않는다.**

여기에 더해, Web3가 필요한 진짜 이유는 다음 문제다.

> **의사결정을 운영하는 기관이 결과와 검증 기록을 동시에 통제하지
> 못하도록 하고, 참여자에게 독립적인 검증 수단을 제공한다.**

------------------------------------------------------------------------

# 20. 사업화 전략

초기 사업 타깃을 **Privacy-Sensitive Group Decision SaaS**로 좁힌다.

## 20.1 데모 진입점 (B2C)

친구·소규모 모임의 식사·여행·일정 결정은 HUSH의 개념을 가장 쉽게
체험하는 **진입점이자 데모**다.

## 20.2 실제 타깃 (B2B2C)

대학·기업·공공기관·행사 운영사가 **필요 이상의 개인 사유를 직접 수집하지
않고도 구성원의 제약을 운영 결정에 반영**하도록 지원한다.

기존 설문: "왜 해당 시간에 참석하기 어렵습니까? □건강 □가족 □종교 □기타"

HUSH: "18시 이후 참석 가능? NO --- Reason: NOT REQUIRED"

운영자에게는 다음만 보여준다.

``` text
EVENT DECISION
Participants 38
Hard Constraints 38/38 ✓
Raw Private Conditions Shared NO
Decision Integrity VERIFIED
```

### 사업적 가치

> **필요한 제약은 수집하되, 필요하지 않은 개인정보는 수집하지 않는다.**

### 예상 고객

기업 HR/People Operations, 대학, 공공기관, 행사 운영사, 워크숍·여행
운영사, 커뮤니티 플랫폼

### 수익 모델 (압축)

1.  조직용 SaaS 구독
2.  Decision Room 사용량 기반 요금
3.  Privacy-Preserving Decision API / Verification 기능

*(DAO Governance 등 현재 사업 방향과 직접 연결되지 않는 항목은 장기 확장
과제로 분리한다.)*

------------------------------------------------------------------------

# 21. 확장 가능성 (Future Work)

HUSH의 핵심 엔진은 특정 식당 추천이 아니라
`Private Constraint → Conflict → Private Negotiation → Consensus → Verification`
구조 자체다. 일정 조율, 여행, 조직 행사, 팀 역할 배정, 커뮤니티
의사결정으로 확장 가능하며, 장기적으로는 프라이버시 보호형 Web3
Governance(DAO)로도 확장할 수 있다.

------------------------------------------------------------------------

# 22. 프로젝트의 기술적 정직성

HUSH는 다음을 주장하지 않는다.

> "블록체인이 공정한 결정을 보장한다." / "AI가 항상 최적의 합의를
> 찾는다." / "모든 비공개 조건이 ZK로 완벽히 검증된다." / "HUSH는 아무도
> 믿지 않아도 되는 완전한 trustless 시스템이다."

대신 MVP가 실제로 보여주는 범위를 명확히 한다.

  ---------------------------------------------------------------------
  구성 요소                          역할
  ---------------------------------- ----------------------------------
  AI                                 자연어 이해와 협상 설명을 지원한다

  Decision Engine                    정형화된 조건의 실제 계산을
                                     담당하며, 오픈소스와 Code Hash로
                                     재현 가능성을 제공한다

  User                               조건 확정과 양보의 최종 권한자다

  Blockchain                         사용자 승인, 조건 버전, 입력 집합,
                                     최종 결과의 provenance를
                                     운영자로부터 독립적으로 고정한다

  ZK PoC (P1)                        특정 비공개 수치 조건의 만족
                                     여부를 공개 없이 검증한다
  ---------------------------------------------------------------------

MVP가 해결하는 신뢰 문제는 명확하다.

> **결정을 운영하는 기관이 결과와 검증 기록을 동시에 통제하지 못하도록
> 하고, 참여자에게 독립적인 검증 수단을 제공한다.**

HUSH 플랫폼 자체에 대한 완전한 탈신뢰화(완전한 탈중앙 거버넌스)는 MVP
범위 밖의 Future Work다.

------------------------------------------------------------------------

# 23. 최종 발표 스토리

발표는 블록체인이나 ZK부터 시작하지 않는다. 새로운 기능 나열이 아니라
**3축**(Private Negotiation → User Control → Independent Verification)만
사용한다.

### 1. 문제

> "네 명이 저녁 장소를 정합니다. 각자 이유는 다르지만, 그 이유를
> 친구들에게 전부 설명하고 싶지는 않습니다."

### 2. ① Private Negotiation

> "HUSH에서는 이유가 아니라 필요한 조건만 비공개로 제출합니다." →
> `NO FEASIBLE SOLUTION` → "하지만 현실의 합의는 여기서부터 시작됩니다."
> → `MINIMUM RELAXATION FOUND — Raw private conditions shared: NO`.
> "HUSH는 누구 때문에 합의가 막혔는지 공개하지 않고, 가장 작은 양보로
> 해결 가능한 당사자에게만 비공개 협상을 요청합니다."

### 3. ② User Control

> `15,000 → 17,000 [ACCEPT]` --- "AI가 마음대로 조건을 바꾸지 않습니다.
> 당사자가 직접 승인합니다."

### 4. 합의

> `HARD CONSTRAINTS 4/4 ✓ · RAW PRIVATE CONDITIONS SHARED: NO · PRIVATE REASONS SHARED: NO · USER-APPROVED RELAXATIONS 1 · DECISION INTEGRITY VERIFIED ✓`

### 5. ③ Independent Verification

> "그런데 이 VERIFIED를, 왜 HUSH의 말만 믿고 받아들여야 할까요?" ---
> Participant Receipt → Public Explorer로 이동해 실제 Transaction과
> Commitment를 직접 조회 → "운영자도, 저희 HUSH도 아니라 여러분이 직접
> 확인한 결과입니다."

### 6. 핵심 메시지

> **"결정을 내린 사람과 그 결정이 정당했다고 증명하는 사람이 같아서는 안
> 됩니다."** "HUSH는 누군가의 비밀을 알아야만 그 사람을 배려할 수 있다는
> 전제를 없애고, 그 배려가 실제로 지켜졌는지 누구나 직접 확인할 수 있게
> 합니다."

------------------------------------------------------------------------

# 24. 최종 요약

HUSH는 **Private Negotiation × User Control × Independent
Verification**의 세 축으로 구성되며, 전 과정에서 **Minimum Necessary
Disclosure**를 프라이버시 원칙으로 적용하는 AI·Web3 집단 협상
시스템이다.

사용자는 경제적 사정, 접근성, 식이 제한, 시간 제약 등 공개하기 어려운
조건을 다른 참가자에게 밝히지 않고 제출한다. AI는 자연어 조건을
구조화하며, 실제 조건 판정은 deterministic Decision Engine이 담당한다.

모든 조건을 만족하는 결과가 존재하지 않을 경우, HUSH는 충돌 구조를
분석해 **최소한의 정보 공개와 최소한의 사용자 양보로 합의를 만들 수 있는
시나리오**를 찾는다. 협상안은 해당 사용자에게만 전달되며 조건 변경은
반드시 사용자가 직접 승인한다.

승인된 조건은 Versioned Commitment로 관리하고, 최종 결정은 사용된 조건
집합·후보 데이터·**Decision Engine 코드 버전**·결과와 연결된 Decision
Commitment로 기록한다. 각 참여자는 **Participant Receipt**를 통해 자신의
조건이 최종 결정에 포함되었는지 HUSH 앱 밖의 **Public Explorer**에서도
직접 검증할 수 있다.

다만 HUSH는 완전한 trustless 시스템이라고 주장하지 않는다.
운영자로부터의 독립적 검증을 우선 목표로 하며, HUSH 플랫폼 자체에 대한
신뢰는 오픈소스 공개와 Immutable Contract로 최소화하고, 완전한
탈중앙화는 향후 과제로 남긴다.

7주 MVP의 핵심 흐름 (P0, 동결):

``` text
Private Input → AI Structuring → User Approval → Commitment → Decision
→ Conflict Detection → Minimum Relaxation → Private Negotiation → User Approval
→ Versioned Re-Commit → Final Decision → Decision Commitment
→ Participant Receipt → Independent Verification
```

가능하면 가격 상한 조건 한 종류에 실제 ZK Proof를 적용해 "조건의 내용은
공개하지 않지만, 해당 조건이 만족됐다는 사실은 검증한다"는 확장 방향까지
PoC(P1)로 보여준다.

------------------------------------------------------------------------

# HUSH

## **비밀은 지키고, 반영됐다는 사실은 증명한다.**

### Private Negotiation → User Control → Independent Verification

> "결정을 내린 사람과 그 결정이 정당했다고 증명하는 사람이 같아서는 안
> 됩니다."
