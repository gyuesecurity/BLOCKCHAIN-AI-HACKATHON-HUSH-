from __future__ import annotations

import re
from typing import Any


class ParseError(ValueError):
    pass


def _number(text: str) -> int | None:
    compact = text.replace(",", "")
    match = re.search(r"(\d+)\s*만\s*원", compact)
    if match:
        return int(match.group(1)) * 10000
    match = re.search(r"(\d{4,})\s*원", compact)
    return int(match.group(1)) if match else None


def parse_korean_constraint(source_text: str) -> dict[str, Any]:
    """Deterministic, explicitly labelled fallback for the pre-screening demo."""
    text = source_text.strip()
    if not text or len(text) > 500:
        raise ParseError("조건은 1자 이상 500자 이하로 입력해 주세요.")

    amount = _number(text)
    if amount is not None and any(word in text for word in ("이하", "넘", "예산", "부담")):
        candidate = {
            "constraint_type": "max_price",
            "priority": "HARD",
            "constraint_value": {"amount": amount, "currency": "KRW"},
            "explanation": f"1인 예상 비용이 {amount:,}원을 넘지 않아야 하는 필수 조건으로 해석했습니다.",
        }
    elif any(word in text for word in ("해산물", "seafood")) and any(
        word in text for word in ("제외", "못", "안 먹", "피해")
    ):
        candidate = {
            "constraint_type": "excluded_category",
            "priority": "HARD",
            "constraint_value": {"categories": ["seafood"]},
            "explanation": "해산물 분류를 제외하는 필수 조건으로 해석했습니다.",
        }
    elif any(word in text for word in ("휠체어", "경사로", "접근성")):
        candidate = {
            "constraint_type": "accessibility_required",
            "priority": "HARD",
            "constraint_value": {"features": ["wheelchair_ramp"]},
            "explanation": "휠체어 경사로가 필요한 필수 접근성 조건으로 해석했습니다.",
        }
    else:
        time_match = re.search(r"([01]?\d|2[0-3])\s*시", text)
        if time_match and any(word in text for word in ("이전", "까지", "귀가", "끝")):
            hour = int(time_match.group(1))
            candidate = {
                "constraint_type": "latest_end_time",
                "priority": "HARD",
                "constraint_value": {"time": f"{hour:02d}:00"},
                "explanation": f"종료 시간이 {hour:02d}:00 이전이어야 하는 필수 조건으로 해석했습니다.",
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
