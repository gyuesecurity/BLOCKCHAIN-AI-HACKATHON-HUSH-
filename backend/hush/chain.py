"""Optional on-chain provenance for the final decision commitment.

Mirrors ``llm.py``: the path is inert unless explicitly configured, every
failure degrades to the honest LOCAL fallback, and nothing here can change a
decision — it only anchors hashes the deterministic engine already produced
(``docs/architecture/07-blockchain-contract.md``).

Scope (Demo-04, minimal): ``createDecision`` -> ``finalizeInputSet`` ->
``commitDecision`` for one decision room on an EVM testnet (default Base
Sepolia). Per-participant condition commitments stay off-chain in this demo.

Enabled when ``HUSH_CHAIN_PRIVATE_KEY`` and ``HUSH_CHAIN_CONTRACT_ADDRESS`` are
set (or ``HUSH_CHAIN_ENABLED`` forces it). ``web3`` comes from the ``[chain]``
optional dependency.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BUILD_ARTIFACT = (
    Path(__file__).resolve().parents[2] / "contracts" / "build" / "HushDecisionRegistry.json"
)

DEFAULT_RPC_URL = "https://sepolia.base.org"
DEFAULT_CHAIN_ID = 84532
DEFAULT_NETWORK_NAME = "Base Sepolia"
DEFAULT_EXPLORER = "https://sepolia.basescan.org"
DEFAULT_TX_TIMEOUT = 150

ENGINE_VERSION = "0.2.0"


class ChainUnavailable(RuntimeError):
    """On-chain anchoring could not run. The caller keeps the LOCAL fallback."""


def _private_key() -> str | None:
    key = os.getenv("HUSH_CHAIN_PRIVATE_KEY")
    return key.strip() if key else None


def _contract_address() -> str | None:
    addr = os.getenv("HUSH_CHAIN_CONTRACT_ADDRESS")
    return addr.strip() if addr else None


def chain_enabled() -> bool:
    flag = os.getenv("HUSH_CHAIN_ENABLED")
    if flag is not None:
        return flag.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_private_key() and _contract_address())


def _rpc_url() -> str:
    return os.getenv("HUSH_CHAIN_RPC_URL", DEFAULT_RPC_URL) or DEFAULT_RPC_URL


def _chain_id() -> int:
    raw = os.getenv("HUSH_CHAIN_ID")
    return int(raw) if raw else DEFAULT_CHAIN_ID


def _network_name() -> str:
    return os.getenv("HUSH_CHAIN_NETWORK_NAME", DEFAULT_NETWORK_NAME) or DEFAULT_NETWORK_NAME


def _explorer_base() -> str:
    return (os.getenv("HUSH_CHAIN_EXPLORER", DEFAULT_EXPLORER) or DEFAULT_EXPLORER).rstrip("/")


def _tx_timeout() -> int:
    raw = os.getenv("HUSH_CHAIN_TX_TIMEOUT")
    return int(raw) if raw else DEFAULT_TX_TIMEOUT


# Public, dependency-free config accessors (used by service.py).
network_name = _network_name
chain_id = _chain_id
rpc_url = _rpc_url


def load_artifact() -> dict[str, Any]:
    if not BUILD_ARTIFACT.exists():
        raise ChainUnavailable(
            f"컨트랙트 빌드 산출물이 없습니다: {BUILD_ARTIFACT} "
            "(scripts/compile_contract.py 실행 필요)"
        )
    return json.loads(BUILD_ARTIFACT.read_text(encoding="utf-8"))


def _b32(hex_value: str) -> bytes:
    text = hex_value[2:] if hex_value.startswith("0x") else hex_value
    raw = bytes.fromhex(text)
    if len(raw) != 32:
        raise ChainUnavailable(f"32바이트 해시가 아닙니다: {hex_value!r}")
    return raw


def _room_key_bytes(room_id: str, run_salt: str) -> bytes:
    from web3 import Web3

    return bytes(Web3.keccak(text=f"{room_id}:{run_salt}"))


def room_key(room_id: str, run_salt: str) -> str:
    """On-chain decision room identifier as a 0x-prefixed 32-byte hex string.

    The demo room id is constant, but the registry stores one write-once record
    per key. A per-demo ``run_salt`` (minted at reset) gives every rehearsal a
    fresh on-chain record so "reset -> re-run" keeps working.
    """
    return "0x" + _room_key_bytes(room_id, run_salt).hex()


def explorer_tx_url(tx_hash: str) -> str:
    return f"{_explorer_base()}/tx/{tx_hash}"


def explorer_address_url(address: str) -> str:
    return f"{_explorer_base()}/address/{address}"


def _client():
    try:
        from web3 import Web3
        from web3.exceptions import Web3Exception  # noqa: F401
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on install
        raise ChainUnavailable("web3 미설치 (pip install 'hush-demo[chain]')") from exc

    key = _private_key()
    address = _contract_address()
    if not key or not address:
        raise ChainUnavailable("HUSH_CHAIN_PRIVATE_KEY / HUSH_CHAIN_CONTRACT_ADDRESS 미설정")

    w3 = Web3(Web3.HTTPProvider(_rpc_url(), request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise ChainUnavailable(f"RPC 연결 실패: {_rpc_url()}")

    artifact = load_artifact()
    account = w3.eth.account.from_key(key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(address), abi=artifact["abi"]
    )
    return w3, account, contract


def _send(w3, account, func, chain_id: int) -> dict[str, Any]:
    """Sign, broadcast, and wait. Returns a per-step provenance entry."""
    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", w3.eth.gas_price)
    try:
        priority = w3.eth.max_priority_fee
    except Exception:  # pragma: no cover - not all RPCs implement it
        priority = w3.to_wei(1, "gwei")

    tx = func.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": chain_id,
            "maxPriorityFeePerGas": priority,
            "maxFeePerGas": base_fee * 2 + priority,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=_tx_timeout())
    hex_hash = tx_hash.hex()
    hex_hash = hex_hash if hex_hash.startswith("0x") else "0x" + hex_hash
    return {
        "step": func.fn_name,
        "tx_hash": hex_hash,
        "status": "CONFIRMED" if receipt["status"] == 1 else "FAILED",
        "block_number": receipt["blockNumber"],
        "explorer_url": explorer_tx_url(hex_hash),
    }


def anchor_final_decision(
    *,
    room_id: str,
    run_salt: str,
    input_set_root: str,
    candidate_dataset_hash: str,
    engine_code_hash: str,
    final_decision_hash: str,
    engine_version: str = ENGINE_VERSION,
) -> dict[str, Any]:
    """Record the final-decision provenance on-chain.

    Returns a ``chain_provenance`` dict with per-transaction status. Raises
    ``ChainUnavailable`` only for setup/connection problems (never for a reverted
    transaction — that comes back as ``status: FAILED`` with an explorer link).
    """
    w3, account, contract = _client()
    chain_id = _chain_id()
    key = _room_key_bytes(room_id, run_salt)

    base = {
        "verification_mode": "ONCHAIN",
        "network": _network_name(),
        "chain_id": chain_id,
        "rpc_url": _rpc_url(),
        "contract_address": contract.address,
        "relayer_address": account.address,
        "decision_room_key": "0x" + key.hex(),
        "engine_version": engine_version,
        "explorer_contract_url": explorer_address_url(contract.address),
        "transactions": [],
    }

    try:
        onchain_commitment = contract.functions.computeDecisionCommitment(
            key,
            _b32(input_set_root),
            _b32(candidate_dataset_hash),
            engine_version,
            _b32(engine_code_hash),
            _b32(final_decision_hash),
        ).call()
    except ChainUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - RPC/ABI surface
        raise ChainUnavailable(f"computeDecisionCommitment 호출 실패: {exc}") from exc

    onchain_commitment = bytes(onchain_commitment)
    base["onchain_decision_commitment"] = "0x" + onchain_commitment.hex()

    steps = [
        contract.functions.createDecision(key),
        contract.functions.finalizeInputSet(
            key,
            _b32(input_set_root),
            _b32(candidate_dataset_hash),
            engine_version,
            _b32(engine_code_hash),
        ),
        contract.functions.commitDecision(
            key,
            _b32(input_set_root),
            _b32(candidate_dataset_hash),
            _b32(engine_code_hash),
            _b32(final_decision_hash),
            onchain_commitment,
        ),
    ]

    for func in steps:
        try:
            entry = _send(w3, account, func, chain_id)
        except ChainUnavailable:
            raise
        except Exception as exc:  # pragma: no cover - RPC/timeout surface
            base["status"] = "FAILED"
            base["transactions"].append(
                {"step": func.fn_name, "status": "FAILED", "error": str(exc)[:200]}
            )
            return base
        base["transactions"].append(entry)
        if entry["status"] != "CONFIRMED":
            base["status"] = "FAILED"
            return base

    base["status"] = "CONFIRMED"
    return base


def read_decision_record(decision_room_key: str) -> dict[str, Any]:
    """Read-only registry lookup used by the receipt verifier."""
    from web3 import Web3

    w3, _account, contract = _client()
    record = contract.functions.verifyDecisionRecord(_b32(decision_room_key)).call()
    fields = [
        "created",
        "input_finalized",
        "decision_committed",
        "input_set_root",
        "candidate_dataset_hash",
        "engine_code_hash",
        "final_decision_hash",
        "decision_commitment",
        "engine_version",
    ]
    out: dict[str, Any] = {}
    for name, value in zip(fields, record):
        if isinstance(value, (bytes, bytearray)):
            out[name] = Web3.to_hex(value)
        else:
            out[name] = value
    out["block_number"] = w3.eth.block_number
    return out
