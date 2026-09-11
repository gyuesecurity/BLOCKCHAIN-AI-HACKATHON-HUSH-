"""On-chain provenance path (Demo-04, minimal scope).

The chain path is optional. These tests must pass whether or not `web3` is
installed; the few that need it are guarded. None of them touch a real network.
"""

from __future__ import annotations

import time

import pytest

from hush import chain
from hush.service import DemoService

try:  # pragma: no cover - trivial
    import web3 as _web3  # noqa: F401

    HAS_WEB3 = True
except ModuleNotFoundError:
    HAS_WEB3 = False


CONFIRMED_PROVENANCE = {
    "status": "CONFIRMED",
    "verification_mode": "ONCHAIN",
    "network": "Ethereum Sepolia",
    "chain_id": 11155111,
    "contract_address": "0x000000000000000000000000000000000000dEaD",
    "relayer_address": "0x000000000000000000000000000000000000BEEF",
    "decision_room_key": "0x" + "22" * 32,
    "onchain_decision_commitment": "0x" + "33" * 32,
    "explorer_contract_url": "https://sepolia.etherscan.io/address/0x0",
    "transactions": [
        {"step": "createDecision", "tx_hash": "0x" + "a1" * 32, "status": "CONFIRMED", "block_number": 1, "explorer_url": "https://x/tx/1"},
        {"step": "finalizeInputSet", "tx_hash": "0x" + "a2" * 32, "status": "CONFIRMED", "block_number": 2, "explorer_url": "https://x/tx/2"},
        {"step": "commitDecision", "tx_hash": "0x" + "a3" * 32, "status": "CONFIRMED", "block_number": 3, "explorer_url": "https://x/tx/3"},
    ],
}


def _complete(svc: DemoService) -> None:
    svc.seed_confirmed_inputs()
    assert svc.run_decision()["status"] == "INFEASIBLE"
    svc.accept_proposal("A")
    assert svc.run_decision()["status"] == "FEASIBLE"


def _wait_for_provenance(svc: DemoService, *, not_status: str = "PENDING", timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        prov = svc.final_record.get("chain_provenance")
        if prov is None or prov.get("status") != not_status:
            return prov
        time.sleep(0.02)
    return svc.final_record.get("chain_provenance")


# --- config gate (no web3 needed) -------------------------------------------------

def test_chain_disabled_by_default(monkeypatch):
    for var in ("HUSH_CHAIN_ENABLED", "HUSH_CHAIN_PRIVATE_KEY", "HUSH_CHAIN_CONTRACT_ADDRESS"):
        monkeypatch.delenv(var, raising=False)
    assert chain.chain_enabled() is False


def test_chain_enabled_when_key_and_address_present(monkeypatch):
    monkeypatch.delenv("HUSH_CHAIN_ENABLED", raising=False)
    monkeypatch.setenv("HUSH_CHAIN_PRIVATE_KEY", "0x" + "11" * 32)
    monkeypatch.setenv("HUSH_CHAIN_CONTRACT_ADDRESS", "0xabc")
    assert chain.chain_enabled() is True


def test_chain_flag_overrides(monkeypatch):
    monkeypatch.setenv("HUSH_CHAIN_ENABLED", "false")
    monkeypatch.setenv("HUSH_CHAIN_PRIVATE_KEY", "0x" + "11" * 32)
    monkeypatch.setenv("HUSH_CHAIN_CONTRACT_ADDRESS", "0xabc")
    assert chain.chain_enabled() is False


def test_b32_rejects_non_32_byte_hash():
    with pytest.raises(chain.ChainUnavailable):
        chain._b32("0x1234")
    assert len(chain._b32("0x" + "ab" * 32)) == 32


# --- default (LOCAL) path: unchanged behaviour -----------------------------------

def test_local_only_demo_has_no_chain_provenance(monkeypatch):
    monkeypatch.delenv("HUSH_CHAIN_ENABLED", raising=False)
    monkeypatch.delenv("HUSH_CHAIN_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("HUSH_CHAIN_CONTRACT_ADDRESS", raising=False)
    svc = DemoService()
    _complete(svc)
    assert svc.final_record["chain_provenance"] is None
    assert "not on-chain" in svc.final_record["verification_label"]
    receipt = svc.receipt("A")
    assert "chain_provenance" not in receipt
    verification = svc.verify("A")
    assert verification["status"] == "VERIFIED"
    assert "not on-chain" in verification["verification_label"]
    assert "onchain" not in verification


# --- enabled but unreachable: honest fallback, demo still completes --------------

def test_enabled_but_unavailable_falls_back_without_breaking_demo(monkeypatch):
    monkeypatch.setenv("HUSH_CHAIN_ENABLED", "true")
    monkeypatch.setattr(chain, "room_key", lambda *a, **k: "0x" + "44" * 32)

    def _boom(**_kwargs):
        raise chain.ChainUnavailable("RPC 연결 실패 (테스트)")

    monkeypatch.setattr(chain, "anchor_final_decision", _boom)

    svc = DemoService()
    _complete(svc)
    prov = _wait_for_provenance(svc)
    assert prov["status"] == "UNAVAILABLE"
    verification = svc.verify("A")
    assert verification["status"] == "VERIFIED"
    assert "not on-chain" in verification["verification_label"]


# --- enabled + confirmed (mocked chain): folds into receipt and verify ----------

def test_confirmed_provenance_flows_into_receipt_and_verify(monkeypatch):
    monkeypatch.setenv("HUSH_CHAIN_ENABLED", "true")
    monkeypatch.setattr(chain, "room_key", lambda *a, **k: CONFIRMED_PROVENANCE["decision_room_key"])
    monkeypatch.setattr(chain, "anchor_final_decision", lambda **_k: dict(CONFIRMED_PROVENANCE))

    svc = DemoService()
    _complete(svc)
    prov = _wait_for_provenance(svc)
    assert prov["status"] == "CONFIRMED"

    receipt = svc.receipt("A")
    assert receipt["chain_provenance"]["status"] == "CONFIRMED"
    assert "on-chain provenance" in receipt["verification_label"]

    shared = svc.shared_state()
    assert shared["onchain"]["status"] == "CONFIRMED"
    assert shared["onchain"]["decision_transaction"]["tx_hash"] == "0x" + "a3" * 32
    # shared screen must still not leak private data
    serialized = str(shared)
    assert "15000" not in serialized and "seafood" not in serialized

    def _record_matches(_key):
        return {
            "created": True,
            "input_finalized": True,
            "decision_committed": True,
            "input_set_root": receipt["input_set_root"],
            "candidate_dataset_hash": receipt["candidate_dataset_hash"],
            "engine_code_hash": receipt["engine_code_hash"],
            "final_decision_hash": receipt["final_decision_hash"],
            "decision_commitment": CONFIRMED_PROVENANCE["onchain_decision_commitment"],
            "engine_version": "0.2.0",
        }

    monkeypatch.setattr(chain, "read_decision_record", _record_matches)
    verification = svc.verify("A")
    assert verification["status"] == "VERIFIED"
    assert verification["onchain"]["verified"] is True
    assert verification["checks"]["onchain_decision_commitment_matches"] is True
    assert verification["checks"]["onchain_final_decision_hash_matches"] is True


def test_onchain_mismatch_makes_verify_invalid(monkeypatch):
    monkeypatch.setenv("HUSH_CHAIN_ENABLED", "true")
    monkeypatch.setattr(chain, "room_key", lambda *a, **k: CONFIRMED_PROVENANCE["decision_room_key"])
    monkeypatch.setattr(chain, "anchor_final_decision", lambda **_k: dict(CONFIRMED_PROVENANCE))
    monkeypatch.setattr(
        chain,
        "read_decision_record",
        lambda _key: {
            "decision_committed": True,
            "input_set_root": "0x" + "de" * 32,  # wrong
            "candidate_dataset_hash": "0x" + "de" * 32,
            "engine_code_hash": "0x" + "de" * 32,
            "final_decision_hash": "0x" + "de" * 32,
            "decision_commitment": "0x" + "de" * 32,
            "engine_version": "0.2.0",
        },
    )
    svc = DemoService()
    _complete(svc)
    _wait_for_provenance(svc)
    verification = svc.verify("A")
    assert verification["status"] == "INVALID"
    assert verification["onchain"]["verified"] is False


@pytest.mark.skipif(not HAS_WEB3, reason="web3 not installed")
def test_room_key_is_deterministic_and_salt_scoped():
    a = chain.room_key("hush-demo-dinner-001", "salt-one")
    b = chain.room_key("hush-demo-dinner-001", "salt-one")
    c = chain.room_key("hush-demo-dinner-001", "salt-two")
    assert a == b != c
    assert a.startswith("0x") and len(a) == 66


def test_read_only_client_does_not_require_private_key(monkeypatch):
    monkeypatch.delenv("HUSH_CHAIN_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("HUSH_CHAIN_CONTRACT_ADDRESS", "0x000000000000000000000000000000000000dEaD")

    class Eth:
        def contract(self, **kwargs):
            return kwargs

    class FakeWeb3:
        HTTPProvider = staticmethod(lambda *args, **kwargs: object())
        to_checksum_address = staticmethod(lambda value: value)

        def __init__(self, _provider):
            self.eth = Eth()

        def is_connected(self):
            return True

    import web3

    monkeypatch.setattr(web3, "Web3", FakeWeb3)
    monkeypatch.setattr(chain, "load_artifact", lambda: {"abi": []})
    _w3, contract = chain._reader()
    assert contract["address"].endswith("dEaD")
