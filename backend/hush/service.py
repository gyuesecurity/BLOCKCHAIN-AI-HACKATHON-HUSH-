from __future__ import annotations

import copy
import logging
import secrets
import threading
from dataclasses import asdict
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any

from . import chain
from .crypto import condition_commitment, hash_json, input_leaf, input_root, keccak256
from .engine import decide
from .fixtures import DEMO_CANDIDATES, DEMO_CONSTRAINTS
from .parser import ParseError, structure_constraint
from .store import StateFormatError, StateStore
from .verification import verify_receipt_data

logger = logging.getLogger("hush.service")

ENGINE_VERSION = "0.2.0"
LOCAL_LABEL = "Demo local verification — not on-chain"

# Everything mutated by the state machine. Snapshotted to the store after every
# mutation and restored on startup so a restart never loses an in-flight
# decision or receipt.
_STATE_FIELDS = (
    "room_status",
    "participants",
    "sessions",
    "drafts",
    "constraint_history",
    "runs",
    "proposal",
    "approvals",
    "final_record",
    "chain_room_salt",
)


def _verification_label(provenance: dict[str, Any] | None) -> str:
    if provenance and provenance.get("status") == "CONFIRMED":
        return f"Local + {provenance.get('network', 'testnet')} on-chain provenance"
    return LOCAL_LABEL


def _public_provenance(prov: dict[str, Any]) -> dict[str, Any]:
    """Chain provenance is all hashes / tx metadata — no private data — but the
    shared screen only needs a curated summary."""
    summary: dict[str, Any] = {
        "status": prov.get("status"),
        "verification_mode": prov.get("verification_mode", "ONCHAIN"),
    }
    for key in (
        "network",
        "chain_id",
        "contract_address",
        "explorer_contract_url",
        "decision_room_key",
        "onchain_decision_commitment",
        "reason",
        "note",
    ):
        if prov.get(key) is not None:
            summary[key] = prov[key]
    transactions = prov.get("transactions") or []
    if transactions:
        commit = next(
            (item for item in transactions if item.get("step") == "commitDecision"),
            transactions[-1],
        )
        summary["decision_transaction"] = {
            field: commit[field]
            for field in ("tx_hash", "status", "block_number", "explorer_url")
            if field in commit
        }
        summary["transaction_count"] = len(transactions)
    return summary


class DemoError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def synchronized(method):
    """Serialize the mutation and snapshot the resulting state to the store."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            result = method(self, *args, **kwargs)
            self._persist()
            return result

    return wrapped


class DemoService:
    room_id = "hush-demo-dinner-001"
    invite_codes = {key: f"HUSH-{key}-2026" for key in ("A", "B", "C", "D")}

    def __init__(self, store: StateStore | None = None) -> None:
        self._lock = RLock()
        self._store = store if store is not None else StateStore()
        with self._lock:
            restored = None
            try:
                restored = self._store.load(self.room_id)
            except StateFormatError:
                logger.exception("저장된 상태를 복원하지 못했습니다 — 새로 시작합니다.")
            if restored is not None:
                self._restore(restored)
                logger.info("이전 방 상태를 복원했습니다 (status=%s).", self.room_status)
            else:
                self.reset()

    # -- persistence -------------------------------------------------------------
    def _snapshot(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in _STATE_FIELDS}

    def _restore(self, snapshot: dict[str, Any]) -> None:
        for field in _STATE_FIELDS:
            setattr(self, field, snapshot.get(field))

    def _persist(self) -> None:
        try:
            self._store.save(self.room_id, self._snapshot())
        except Exception:  # persistence must never break the demo flow
            logger.exception("방 상태 저장에 실패했습니다 (계속 진행).")

    def store_info(self) -> dict[str, Any]:
        return self._store.describe()

    @synchronized
    def reset(self) -> dict[str, Any]:
        self.room_status = "COLLECTING"
        self.participants = {
            key: {
                "participant_pseudonym": key,
                "status": "INVITED",
                "input_status": "PENDING_INPUT",
            }
            for key in ("A", "B", "C", "D")
        }
        self.sessions: dict[str, str] = {}
        self.drafts: dict[str, dict[str, Any]] = {}
        self.constraint_history: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.proposal: dict[str, Any] | None = None
        self.approvals: list[dict[str, Any]] = []
        self.final_record: dict[str, Any] | None = None
        # 컨트랙트 레지스트리는 room 키마다 write-once다. 데모를 reset 후 다시
        # 돌려도 새 on-chain record가 생기도록 리허설마다 새 salt를 만든다.
        self.chain_room_salt = secrets.token_hex(16)
        return self.shared_state()

    @synchronized
    def join(self, participant: str, invite_code: str) -> dict[str, Any]:
        self._participant(participant)
        if not secrets.compare_digest(invite_code, self.invite_codes[participant]):
            raise DemoError(404, "NOT_FOUND", "초대 정보를 확인할 수 없습니다.")
        token = secrets.token_urlsafe(32)
        self.sessions[token] = participant
        self.participants[participant]["status"] = "JOINED"
        return {
            "participant_pseudonym": participant,
            "participant_session": token,
            "status": "JOINED",
        }

    def validate_session(self, participant: str, token: str | None) -> str:
        normalized = participant.upper()
        self._participant(normalized)
        if not token or self.sessions.get(token) != normalized:
            raise DemoError(404, "NOT_FOUND", "참가자 전용 정보를 찾을 수 없습니다.")
        return normalized

    @synchronized
    def parse_input(self, participant: str, source_text: str) -> dict[str, Any]:
        self._participant(participant)
        if self.room_status != "COLLECTING":
            raise DemoError(409, "INVALID_STATE", "현재는 새 조건을 입력할 수 없습니다.")
        try:
            parsed = structure_constraint(source_text)
        except ParseError as exc:
            raise DemoError(422, "AI_PARSE_FAILED", str(exc)) from exc
        draft_id = "draft-" + secrets.token_hex(8)
        self.drafts[draft_id] = {"participant": participant, **parsed}
        return {"draft_id": draft_id, **parsed}

    @synchronized
    def confirm_draft(self, participant: str, draft_id: str) -> dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if not draft or draft["participant"] != participant:
            raise DemoError(404, "NOT_FOUND", "확정할 조건 초안을 찾을 수 없습니다.")
        if self.participants[participant]["input_status"] == "INPUT_CONFIRMED":
            raise DemoError(409, "ALREADY_CONFIRMED", "이미 조건을 확정했습니다.")
        item = {
            "constraint_id": f"constraint-{participant.lower()}-1",
            "participant_pseudonym": participant,
            **copy.deepcopy(draft["structured_candidate"]),
            "source_text": draft["source_text"],
            "constraint_version_id": f"constraint-{participant.lower()}-1-v1",
            "constraint_version": 1,
            "status": "ACTIVE",
            "salt": "0x" + secrets.token_hex(32),
        }
        item.pop("explanation", None)
        item["condition_commitment"] = self._commitment(item)
        self.constraint_history.append(item)
        self.participants[participant].update(
            {"status": "ACTIVE", "input_status": "INPUT_CONFIRMED"}
        )
        del self.drafts[draft_id]
        if all(value["input_status"] == "INPUT_CONFIRMED" for value in self.participants.values()):
            self.room_status = "READY"
        return {
            "constraint": self._without_secret(item),
            "input_status": "INPUT_CONFIRMED",
            "evidence_mode": "LOCAL",
        }

    @synchronized
    def seed_confirmed_inputs(self) -> dict[str, Any]:
        if self.room_status != "COLLECTING":
            raise DemoError(409, "INVALID_STATE", "입력을 확정할 수 없는 상태입니다.")
        self.constraint_history = []
        for fixture in DEMO_CONSTRAINTS:
            item = copy.deepcopy(fixture)
            item.update(
                {
                    "constraint_version_id": item["constraint_id"] + "-v1",
                    "constraint_version": 1,
                    "status": "ACTIVE",
                    "source_text": "관리자용 고정 Demo fixture",
                    "salt": "0x" + secrets.token_hex(32),
                }
            )
            item["condition_commitment"] = self._commitment(item)
            self.constraint_history.append(item)
            self.participants[item["participant_pseudonym"]].update(
                {"status": "ACTIVE", "input_status": "INPUT_CONFIRMED"}
            )
        self.room_status = "READY"
        return self.shared_state()

    def _active_constraints(self) -> list[dict[str, Any]]:
        return [item for item in self.constraint_history if item["status"] == "ACTIVE"]

    def _commitment(self, item: dict[str, Any]) -> str:
        return condition_commitment(self._condition_payload(item), item["salt"])

    def _condition_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision_room_id": self.room_id,
            "participant_pseudonym": item["participant_pseudonym"],
            "constraint_id": item["constraint_id"],
            "constraint_version": item["constraint_version"],
            "constraint_type": item["constraint_type"],
            "priority": item["priority"],
            "constraint_value": item["constraint_value"],
        }

    def shared_state(self) -> dict[str, Any]:
        provenance = self.final_record.get("chain_provenance") if self.final_record else None
        result: dict[str, Any] = {
            "decision_room_id": self.room_id,
            "title": "4인 저녁 식사 장소 결정",
            "status": self.room_status,
            "required_participant_count": 4,
            "participant_count": 4,
            "input_confirmed_participant_count": sum(
                value["input_status"] == "INPUT_CONFIRMED"
                for value in self.participants.values()
            ),
            "verification_mode": "LOCAL",
            "verification_label": _verification_label(provenance),
        }
        if self.room_status == "NEGOTIATING":
            result["decision_status"] = "PRIVATE_ADJUSTMENT_AVAILABLE"
        elif self.room_status == "COMPLETED":
            result.update(
                {
                    "decision_status": "FINAL_DECISION_COMMITTED_LOCALLY",
                    "final_candidate": self.final_record["candidate"],
                    "user_approved_relaxation_count": len(self.approvals),
                }
            )
            if provenance:
                result["onchain"] = _public_provenance(provenance)
        else:
            result["decision_status"] = self.room_status
        return result

    def private_state(self, participant: str) -> dict[str, Any]:
        own = [
            self._without_secret(item)
            for item in self.constraint_history
            if item["participant_pseudonym"] == participant
        ]
        proposal = (
            copy.deepcopy(self.proposal)
            if self.proposal and self.proposal["participant_pseudonym"] == participant
            else None
        )
        return {
            "participant": self.participants[participant],
            "constraint_version_history": own,
            "proposal": proposal,
        }

    @staticmethod
    def _without_secret(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "salt"}

    @synchronized
    def run_decision(self) -> dict[str, Any]:
        if self.room_status != "READY":
            raise DemoError(409, "INVALID_STATE", "모든 입력 확정 또는 완화 승인이 필요합니다.")
        run_id = f"decision-run-{len(self.runs) + 1}"
        frozen = copy.deepcopy(self._active_constraints())
        input_entries = []
        for item in frozen:
            participant_input_id = f'{item["constraint_version_id"]}-input'
            leaf_payload = {
                "decision_room_id": self.room_id,
                "decision_run_id": run_id,
                "participant_input_id": participant_input_id,
                "input_mode": "CONSTRAINED",
                "constraint_version_id": item["constraint_version_id"],
                "condition_commitment": item["condition_commitment"],
            }
            input_entries.append(
                {
                    **leaf_payload,
                    "participant_pseudonym": item["participant_pseudonym"],
                    "constraint_id": item["constraint_id"],
                    "input_set_leaf": input_leaf(leaf_payload),
                }
            )
        leaves = [item["input_set_leaf"] for item in input_entries]
        result = decide(DEMO_CANDIDATES, frozen)
        record = {
            "decision_run_id": run_id,
            "frozen_constraints": frozen,
            "input_entries": input_entries,
            "input_set_leaves": sorted(leaves),
            "input_set_root": input_root(leaves),
            "engine_result": asdict(result),
        }
        self.runs.append(record)
        if result.result_type == "INFEASIBLE":
            if result.proposal is None:
                self.room_status = "CLOSED"
                return {"status": "INFEASIBLE", "decision_status": "NO_VALID_RELAXATION"}
            self.proposal = {
                **result.proposal,
                "relaxation_proposal_id": f"proposal-{len(self.runs)}",
                "constraint_version_id": next(
                    item["constraint_version_id"]
                    for item in frozen
                    if item["constraint_id"] == result.proposal["constraint_id"]
                ),
                "status": "PROPOSED",
            }
            self.room_status = "NEGOTIATING"
            return {
                "decision_run_id": run_id,
                "status": "INFEASIBLE",
                "decision_status": "PRIVATE_ADJUSTMENT_AVAILABLE",
            }
        self._finalize_local(record, result.selected_candidate_id)
        return {
            "decision_run_id": run_id,
            "status": "FEASIBLE",
            "decision_status": "FINAL_DECISION_COMMITTED_LOCALLY",
            "selected_candidate_id": result.selected_candidate_id,
        }

    @synchronized
    def accept_proposal(self, participant: str) -> dict[str, Any]:
        if self.room_status != "NEGOTIATING" or not self.proposal:
            raise DemoError(409, "INVALID_STATE", "승인할 협상안이 없습니다.")
        if self.proposal["participant_pseudonym"] != participant:
            raise DemoError(404, "NOT_FOUND", "협상안을 찾을 수 없습니다.")
        if self.proposal["status"] != "PROPOSED":
            raise DemoError(409, "ALREADY_DECIDED", "이미 처리된 협상안입니다.")
        old = next(
            item
            for item in self.constraint_history
            if item["constraint_version_id"] == self.proposal["constraint_version_id"]
            and item["status"] == "ACTIVE"
        )
        successor = copy.deepcopy(old)
        successor.update(
            {
                "constraint_version_id": old["constraint_id"] + f'-v{old["constraint_version"] + 1}',
                "constraint_version": old["constraint_version"] + 1,
                "constraint_value": copy.deepcopy(self.proposal["proposed_constraint_value"]),
                "status": "ACTIVE",
                "salt": "0x" + secrets.token_hex(32),
                "supersedes_constraint_version_id": old["constraint_version_id"],
            }
        )
        successor["condition_commitment"] = self._commitment(successor)
        old["status"] = "SUPERSEDED"
        self.constraint_history.append(successor)
        approval = {
            "user_approval_id": "approval-" + secrets.token_hex(8),
            "participant_pseudonym": participant,
            "relaxation_proposal_id": self.proposal["relaxation_proposal_id"],
            "decision": "ACCEPTED",
        }
        self.approvals.append(approval)
        self.proposal["status"] = "ACCEPTED"
        self.room_status = "READY"
        return {
            **approval,
            "new_constraint_version_id": successor["constraint_version_id"],
            "constraint_version": successor["constraint_version"],
            "condition_commitment": successor["condition_commitment"],
            "evidence_mode": "LOCAL",
        }

    @synchronized
    def reject_proposal(self, participant: str) -> dict[str, Any]:
        if not self.proposal or self.proposal["participant_pseudonym"] != participant:
            raise DemoError(404, "NOT_FOUND", "협상안을 찾을 수 없습니다.")
        self.proposal["status"] = "REJECTED"
        self.room_status = "CLOSED"
        return {"decision": "REJECTED", "status": "CLOSED"}

    def _finalize_local(self, run: dict[str, Any], candidate_id: str | None) -> None:
        candidate = next(item for item in DEMO_CANDIDATES if item["candidate_id"] == candidate_id)
        dataset_hash = hash_json(DEMO_CANDIDATES)
        engine_hash = keccak256(Path(__file__).with_name("engine.py").read_bytes())
        final_id = "final-decision-001"
        final_hash = hash_json(
            {
                "protocol": "HUSH",
                "schema_version": "1",
                "final_decision_id": final_id,
                "candidate_id": candidate_id,
                "input_set_root": run["input_set_root"],
                "candidate_dataset_hash": dataset_hash,
                "engine_version": "0.2.0",
                "engine_code_hash": engine_hash,
            }
        )
        decision_commitment = hash_json(
            {
                "protocol": "HUSH",
                "schema_version": "1",
                "verification_mode": "LOCAL",
                "decision_room_id": self.room_id,
                "input_set_root": run["input_set_root"],
                "candidate_dataset_hash": dataset_hash,
                "engine_version": ENGINE_VERSION,
                "engine_code_hash": engine_hash,
                "final_decision_hash": final_hash,
            }
        )
        provenance = self._start_onchain_anchor(final_id, run["input_set_root"], dataset_hash, engine_hash, final_hash)
        self.final_record = {
            "final_decision_id": final_id,
            "candidate": copy.deepcopy(candidate),
            "candidate_dataset_hash": dataset_hash,
            "engine_version": ENGINE_VERSION,
            "engine_code_hash": engine_hash,
            "final_decision_hash": final_hash,
            "decision_commitment": decision_commitment,
            "run": run,
            "verification_mode": "LOCAL",
            "verification_label": _verification_label(provenance),
            "chain_provenance": provenance,
        }
        self.room_status = "COMPLETED"

    def _start_onchain_anchor(
        self,
        final_id: str,
        input_set_root: str,
        dataset_hash: str,
        engine_hash: str,
        final_hash: str,
    ) -> dict[str, Any] | None:
        """Kick off on-chain anchoring in the background (Demo-04, minimal scope).

        Returns the initial ``PENDING`` provenance immediately so the demo never
        blocks on block confirmation; a daemon thread fills in the transaction
        results. Returns ``None`` (LOCAL only) when the chain path is not
        configured. Nothing here can change the decision.
        """
        if not chain.chain_enabled():
            return None

        salt = self.chain_room_salt
        try:
            room_key = chain.room_key(self.room_id, salt)
        except chain.ChainUnavailable as exc:
            return {"status": "UNAVAILABLE", "verification_mode": "LOCAL", "reason": str(exc)[:200]}

        params = {
            "room_id": self.room_id,
            "run_salt": salt,
            "input_set_root": input_set_root,
            "candidate_dataset_hash": dataset_hash,
            "engine_code_hash": engine_hash,
            "final_decision_hash": final_hash,
            "engine_version": ENGINE_VERSION,
        }

        def worker() -> None:
            try:
                result = chain.anchor_final_decision(**params)
            except chain.ChainUnavailable as exc:
                result = {"status": "UNAVAILABLE", "verification_mode": "LOCAL", "reason": str(exc)[:200]}
            except Exception as exc:  # pragma: no cover - defensive
                result = {"status": "FAILED", "verification_mode": "LOCAL", "reason": str(exc)[:200]}
            with self._lock:
                if self.final_record and self.final_record.get("final_decision_id") == final_id:
                    self.final_record["chain_provenance"] = result
                    self.final_record["verification_label"] = _verification_label(result)
                    self._persist()

        threading.Thread(target=worker, name="hush-onchain-anchor", daemon=True).start()
        return {
            "status": "PENDING",
            "verification_mode": "ONCHAIN",
            "network": chain.network_name(),
            "chain_id": chain.chain_id(),
            "decision_room_key": room_key,
            "note": "on-chain 기록 진행 중 — 확정되면 CONFIRMED로 바뀝니다.",
            "transactions": [],
        }

    def receipt(self, participant: str, include_private: bool = False) -> dict[str, Any]:
        if not self.final_record:
            raise DemoError(409, "NOT_READY", "최종 결정이 아직 없습니다.")
        record = self.final_record
        own_constraints = {
            item["constraint_version_id"]: item
            for item in record["run"]["frozen_constraints"]
            if item["participant_pseudonym"] == participant
        }
        own_entries = [
            {key: value for key, value in entry.items() if key != "participant_pseudonym"}
            for entry in record["run"]["input_entries"]
            if entry["participant_pseudonym"] == participant
        ]
        private_material = [
            {
                "constraint_version_id": version_id,
                "condition_payload": self._condition_payload(item),
                "salt": item["salt"],
            }
            for version_id, item in own_constraints.items()
        ]
        receipt = {
            "participant_pseudonym": participant,
            "final_decision_id": record["final_decision_id"],
            "decision_run_id": record["run"]["decision_run_id"],
            "participant_inputs": own_entries,
            "input_set_leaves": record["run"]["input_set_leaves"],
            "input_set_root": record["run"]["input_set_root"],
            "candidate_dataset_hash": record["candidate_dataset_hash"],
            "engine_version": record["engine_version"],
            "engine_code_hash": record["engine_code_hash"],
            "final_decision_hash": record["final_decision_hash"],
            "decision_commitment": record["decision_commitment"],
            "candidate": record["candidate"],
            "verification_mode": record["verification_mode"],
            "verification_label": record["verification_label"],
            "candidate_dataset_uri": "fixtures/demo-candidates-v1.json",
            "engine_artifact_uri": "backend/hush/engine.py",
            "verification_script_uri": "scripts/verify_receipt.py",
        }
        if record.get("chain_provenance"):
            receipt["chain_provenance"] = copy.deepcopy(record["chain_provenance"])
        if include_private:
            receipt["private_verification_material"] = private_material
        return receipt

    def verify(self, participant: str) -> dict[str, Any]:
        receipt = self.receipt(participant, include_private=True)
        result = verify_receipt_data(
            receipt,
            DEMO_CANDIDATES,
            Path(__file__).with_name("engine.py").read_bytes(),
        )
        provenance = self.final_record.get("chain_provenance") if self.final_record else None
        response = {
            **result,
            "verification_mode": "LOCAL",
            "verification_label": _verification_label(provenance),
        }
        if provenance and provenance.get("status") == "CONFIRMED":
            response["onchain"] = self._verify_onchain(receipt, provenance)
            if response["onchain"].get("checks"):
                result["checks"].update(response["onchain"]["checks"])
                response["checks"] = result["checks"]
                response["status"] = "VERIFIED" if all(result["checks"].values()) else "INVALID"
        elif provenance:
            response["onchain"] = {"status": provenance.get("status"), "verified": False}
        return response

    @staticmethod
    def _verify_onchain(receipt: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
        """Re-read the registry and confirm it matches the receipt.

        Chain read failures never fail the overall receipt (local verification is
        independent and complete) — they surface as an explicit skip note.
        """
        try:
            record = chain.read_decision_record(provenance["decision_room_key"])
        except chain.ChainUnavailable as exc:
            return {"status": "CONFIRMED", "verified": False, "note": f"on-chain 재조회 실패: {exc}"[:200]}

        def _eq(a: str | None, b: str | None) -> bool:
            return bool(a) and bool(b) and a.lower() == b.lower()

        checks = {
            "onchain_decision_committed": record.get("decision_committed") is True,
            "onchain_decision_commitment_matches": _eq(
                record.get("decision_commitment"), provenance.get("onchain_decision_commitment")
            ),
            "onchain_input_set_root_matches": _eq(
                record.get("input_set_root"), receipt["input_set_root"]
            ),
            "onchain_final_decision_hash_matches": _eq(
                record.get("final_decision_hash"), receipt["final_decision_hash"]
            ),
            "onchain_candidate_dataset_hash_matches": _eq(
                record.get("candidate_dataset_hash"), receipt["candidate_dataset_hash"]
            ),
            "onchain_engine_code_hash_matches": _eq(
                record.get("engine_code_hash"), receipt["engine_code_hash"]
            ),
        }
        return {
            "status": "CONFIRMED",
            "verified": all(checks.values()),
            "checks": checks,
            "record": record,
        }

    def _participant(self, participant: str) -> None:
        if participant not in self.participants:
            raise DemoError(404, "NOT_FOUND", "참가자를 찾을 수 없습니다.")
