from __future__ import annotations

import json
from typing import Any

from Crypto.Hash import keccak


def canonical_json(value: Any) -> bytes:
    """Serialize the P0 JSON subset deterministically.

    P0 payloads intentionally use integers, strings, booleans, lists and objects
    only. Floats are rejected because cross-language number formatting is unsafe.
    """

    def reject_float(item: Any) -> None:
        if isinstance(item, float):
            raise ValueError("floating-point values are not allowed")
        if isinstance(item, dict):
            for child in item.values():
                reject_float(child)
        elif isinstance(item, list):
            for child in item:
                reject_float(child)

    reject_float(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def keccak256(value: bytes) -> str:
    digest = keccak.new(digest_bits=256)
    digest.update(value)
    return "0x" + digest.hexdigest()


def hash_json(value: Any) -> str:
    return keccak256(canonical_json(value))


def condition_commitment(payload: dict[str, Any], salt: str) -> str:
    if not salt.startswith("0x") or len(salt) != 66:
        raise ValueError("salt must be a 32-byte 0x-prefixed hex string")
    return hash_json(
        {
            "protocol": "HUSH",
            "schema_version": "1",
            **payload,
            "salt": salt.lower(),
        }
    )


def input_leaf(payload: dict[str, Any]) -> str:
    return hash_json(
        {"protocol": "HUSH", "schema_version": "1", **payload}
    )


def input_root(leaves: list[str]) -> str:
    normalized = sorted(leaves)
    if len(set(normalized)) != len(normalized):
        raise ValueError("duplicate input leaf")
    return hash_json(normalized)

