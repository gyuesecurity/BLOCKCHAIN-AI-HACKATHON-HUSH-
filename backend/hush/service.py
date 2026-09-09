from __future__ import annotations

import copy
import secrets
from dataclasses import asdict
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any

from .crypto import condition_commitment, hash_json, input_leaf, input_root, keccak256
from .engine import decide
from .fixtures import DEMO_CANDIDATES, DEMO_CONSTRAINTS
from .parser import ParseError, structure_constraint
from .verification import verify_receipt_data


class DemoError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


class DemoService:
    room_id = "hush-demo-dinner-001"
    invite_codes = {key: f"HUSH-{key}-2026" for key in ("A", "B", "C", "D")}

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

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
            "verification_label": "Demo local verification — not on-chain",
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
                "engine_version": "0.2.0",
                "engine_code_hash": engine_hash,
                "final_decision_hash": final_hash,
            }
        )
        self.final_record = {
            "final_decision_id": final_id,
            "candidate": copy.deepcopy(candidate),
            "candidate_dataset_hash": dataset_hash,
            "engine_version": "0.2.0",
            "engine_code_hash": engine_hash,
            "final_decision_hash": final_hash,
            "decision_commitment": decision_commitment,
            "run": run,
            "verification_mode": "LOCAL",
            "verification_label": "Demo local verification — not on-chain",
        }
        self.room_status = "COMPLETED"

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
        return {
            **result,
            "verification_mode": "LOCAL",
            "verification_label": "Demo local verification — not on-chain",
        }

    def _participant(self, participant: str) -> None:
        if participant not in self.participants:
            raise DemoError(404, "NOT_FOUND", "참가자를 찾을 수 없습니다.")
