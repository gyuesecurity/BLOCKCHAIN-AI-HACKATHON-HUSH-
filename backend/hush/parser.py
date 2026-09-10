from __future__ import annotations

import re
from typing import Any


class ParseError(ValueError):
    pass


def structure_constraint(source_text: str) -> dict[str, Any]:
    """자연어 → 구조화 제약. 실제 LLM 우선, 실패 시 규칙 기반 fallback.

    반환 shape은 두 경로 모두 동일하다:
    `{parser_mode, is_ai, notice, source_text, structured_candidate, ...}`.
    LLM 경로는 `parser_mode="LLM"`, `is_ai=True`, `model`을 추가로 담고,
    fallback 경로는 `parser_mode="DEMO_RULE_PARSER"`, `is_ai=False`를 유지한다.
    두 경로 모두 실패하면 `ParseError`.
    """
    text = source_text.strip()
    if not text or len(text) > 500:
        raise ParseError("조건은 1자 이상 500자 이하로 입력해 주세요.")

    from .llm import LLMUnavailable, llm_enabled, structure_with_llm

    if not llm_enabled():
        return parse_korean_constraint(text)

    try:
        return structure_with_llm(text)
    except LLMUnavailable as exc:
        result = parse_korean_constraint(text)
        result["llm_fallback"] = True
        result["notice"] = (
            "LLM 구조화에 실패해 규칙 기반 fallback으로 처리했습니다. "
            "결과는 확정 전 draft입니다."
        )
        result["llm_fallback_reason"] = str(exc)[:120]
        return result


def _number(text: str) -> int | None:
    compact = text.replace(",", "")
    match = re.search(r"(\d+)\s*만\s*원", compact)
    if match:
        return int(match.group(1)) * 10000
    match = re.search(r"(\d{4,})\s*원", compact)
    return int(match.group(1)) if match else None


_SOFT_HINTS = ("가능하면", "가급적", "웬만하면", "왠만하면", "되도록", "이왕이면", "선호")


def _priority(text: str) -> str:
    """선호/가급적 뉘앙스면 SOFT, 그렇지 않으면 HARD(기본값). llm.py와 동일한 규칙."""
    return "SOFT" if any(hint in text for hint in _SOFT_HINTS) else "HARD"


def _priority_label(priority: str) -> str:
    return "선호(SOFT)" if priority == "SOFT" else "필수(HARD)"


def parse_korean_constraint(source_text: str) -> dict[str, Any]:
    """Deterministic, explicitly labelled fallback for the pre-screening demo."""
    text = source_text.strip()
    if not text or len(text) > 500:
        raise ParseError("조건은 1자 이상 500자 이하로 입력해 주세요.")

    priority = _priority(text)
    label = _priority_label(priority)

    amount = _number(text)
    if amount is not None and any(word in text for word in ("이하", "넘", "예산", "부담")):
        candidate = {
            "constraint_type": "max_price",
            "priority": priority,
            "constraint_value": {"amount": amount, "currency": "KRW"},
            "explanation": f"1인 예상 비용이 {amount:,}원을 넘지 않아야 하는 {label} 조건으로 해석했습니다.",
        }
    elif any(word in text for word in ("해산물", "seafood")) and any(
        word in text for word in ("제외", "못", "안 먹", "피해", "피하")
    ):
        candidate = {
            "constraint_type": "excluded_category",
            "priority": priority,
            "constraint_value": {"categories": ["seafood"]},
            "explanation": f"해산물 분류를 제외하는 {label} 조건으로 해석했습니다.",
        }
    elif any(word in text for word in ("휠체어", "경사로", "접근성")):
        candidate = {
            "constraint_type": "accessibility_required",
            "priority": priority,
            "constraint_value": {"features": ["wheelchair_ramp"]},
            "explanation": f"휠체어 경사로가 필요한 {label} 접근성 조건으로 해석했습니다.",
        }
    else:
        time_match = re.search(r"([01]?\d|2[0-3])\s*시", text)
        if time_match and any(word in text for word in ("이전", "까지", "귀가", "끝")):
            hour = int(time_match.group(1))
            candidate = {
                "constraint_type": "latest_end_time",
                "priority": priority,
                "constraint_value": {"time": f"{hour:02d}:00"},
                "explanation": f"종료 시간이 {hour:02d}:00 이전이어야 하는 {label} 조건으로 해석했습니다.",
            }
        else:
            raise ParseError("지원하는 가격·해산물 제외·접근성·종료 시간 조건으로 해석하지 못했습니다.")

    return {
        "parser_mode": "DEMO_RULE_PARSER",
        "is_ai": False,
        "notice": "외부 LLM 미연결 상태의 결정적 Demo fallback입니다.",
        "source_text": text,
        "structured_candidate": candidate,
    }
