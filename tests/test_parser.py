import pytest

from hush.parser import ParseError, parse_korean_constraint


@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        ("15,000원을 넘으면 부담스러워요", "max_price"),
        ("해산물은 못 먹어요", "excluded_category"),
        ("휠체어 경사로가 필요해요", "accessibility_required"),
        ("21시 이전에 끝나야 해요", "latest_end_time"),
    ],
)
def test_supported_demo_parsing(text, expected_type):
    parsed = parse_korean_constraint(text)
    assert parsed["structured_candidate"]["constraint_type"] == expected_type
    assert parsed["is_ai"] is False


def test_unsupported_text_is_not_silently_confirmed():
    with pytest.raises(ParseError):
        parse_korean_constraint("아무거나 좋아요")

