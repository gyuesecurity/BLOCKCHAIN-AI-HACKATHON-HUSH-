from __future__ import annotations

import copy
import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .crypto import condition_commitment, hash_json, input_leaf, input_root, keccak256
from .engine import decide
from .fixtures import DEMO_CANDIDATES, DEMO_CONSTRAINTS


class DemoError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class DemoService:
    room_id = "hush-demo-dinner-001"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.room_status = "COLLECTING"
        self.participants = {
            key: {"participant_pseudonym": key, "input_status": "PENDING_INPUT"}
            for key in ("A", "B", "C", "D")
        }
        self.constraints: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.proposal: dict[str, Any] | None = None
        self.final_record: dict[str, Any] | None = None
        return self.shared_state()

    def seed_confirmed_inputs(self) -> dict[str, Any]:
        if self.room_status != "COLLECTING":
            raise DemoError(409, "INVALID_STATE", "입력을 확정할 수 없는 상태입니다.")
        self.constraints = []
        for fixture in DEMO_CONSTRAINTS:
            item = copy.deepcopy(fixture)
            item.update(
                {
                    "constraint_version_id": item["constraint_id"] + "-v1",
                    "constraint_version": 1,
                    "status": "ACTIVE",
                    "salt": "0x" + secrets.token_hex(32),
                }
            )
            item["condition_commitment"] = self._commitment(item)
            self.constraints.append(item)
            self.participants[item["participant_pseudonym"]]["input_status"] = "INPUT_CONFIRMED"
        self.room_status = "READY"
        return self.shared_state()

    def _commitment(self, item: dict[str, Any]) -> str:
        return condition_commitment(
            {
                "decision_room_id": self.room_id,
                "participant_pseudonym": item["participant_pseudonym"],
                "constraint_id": item["constraint_id"],
                "constraint_version": item["constraint_version"],
                "constraint_type": item["constraint_type"],
                "priority": item["priority"],
                "constraint_value": item["constraint_value"],
            },
            item["salt"],
        )

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
                }
            )
        else:
            result["decision_status"] = self.room_status
        return result

    def private_state(self, participant: str) -> dict[str, Any]:
        self._participant(participant)
        own = [self._public_constraint(item) for item in self.constraints if item["participant_pseudonym"] == participant]
        proposal = copy.deepcopy(self.proposal) if self.proposal and self.proposal["participant_pseudonym"] == participant else None
        return {"participant": self.participants[participant], "constraints": own, "proposal": proposal}

    @staticmethod
    def _public_constraint(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "salt"}

    def run_decision(self) -> dict[str, Any]:
        if self.room_status != "READY":
            raise DemoError(409, "INVALID_STATE", "모든 입력 확정 또는 완화 승인이 필요합니다.")
        run_number = len(self.runs) + 1
        run_id = f"decision-run-{run_number}"
        frozen = copy.deepcopy(self.constraints)
        leaves = [
            input_leaf(
                {
                    "decision_room_id": self.room_id,
                    "decision_run_id": run_id,
                    "participant_input_id": f'{item["constraint_version_id"]}-input',
                    "input_mode": "CONSTRAINED",
                    "constraint_version_id": item["constraint_version_id"],
                    "condition_commitment": item["condition_commitment"],
                }
            )
            for item in frozen
        ]
        result = decide(DEMO_CANDIDATES, frozen)
        record = {
            "decision_run_id": run_id,
            "frozen_constraints": frozen,
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
                "relaxation_proposal_id": f"proposal-{run_number}",
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

    def accept_proposal(self, participant: str) -> dict[str, Any]:
        self._participant(participant)
        if self.room_status != "NEGOTIATING" or not self.proposal:
            raise DemoError(409, "INVALID_STATE", "승인할 협상안이 없습니다.")
        if self.proposal["participant_pseudonym"] != participant:
            raise DemoError(404, "NOT_FOUND", "협상안을 찾을 수 없습니다.")
        if self.proposal["status"] != "PROPOSED":
            raise DemoError(409, "ALREADY_DECIDED", "이미 처리된 협상안입니다.")
        old = next(item for item in self.constraints if item["constraint_id"] == self.proposal["constraint_id"])
        old["status"] = "SUPERSEDED"
        successor = copy.deepcopy(old)
        successor.update(
            {
                "constraint_version_id": old["constraint_id"] + "-v2",
                "constraint_version": 2,
                "constraint_value": copy.deepcopy(self.proposal["proposed_constraint_value"]),
                "status": "ACTIVE",
                "salt": "0x" + secrets.token_hex(32),
            }
        )
        successor["condition_commitment"] = self._commitment(successor)
        self.constraints = [item for item in self.constraints if item["status"] == "ACTIVE"] + [successor]
        self.proposal["status"] = "ACCEPTED"
        self.room_status = "READY"
        return {
            "decision": "ACCEPTED",
            "new_constraint_version_id": successor["constraint_version_id"],
            "constraint_version": 2,
            "condition_commitment": successor["condition_commitment"],
            "evidence_mode": "LOCAL",
        }

    def reject_proposal(self, participant: str) -> dict[str, Any]:
        self._participant(participant)
        if not self.proposal or self.proposal["participant_pseudonym"] != participant:
            raise DemoError(404, "NOT_FOUND", "협상안을 찾을 수 없습니다.")
        self.proposal["status"] = "REJECTED"
        self.room_status = "CLOSED"
        return {"decision": "REJECTED", "status": "CLOSED"}

    def _finalize_local(self, run: dict[str, Any], candidate_id: str | None) -> None:
        candidate = next(item for item in DEMO_CANDIDATES if item["candidate_id"] == candidate_id)
        dataset_hash = hash_json(DEMO_CANDIDATES)
        engine_path = Path(__file__).with_name("engine.py")
        engine_hash = keccak256(engine_path.read_bytes())
        final_id = "final-decision-001"
        final_hash = hash_json(
            {
                "protocol": "HUSH",
                "schema_version": "1",
                "final_decision_id": final_id,
                "candidate_id": candidate_id,
                "input_set_root": run["input_set_root"],
                "candidate_dataset_hash": dataset_hash,
                "engine_version": "0.1.0",
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
                "engine_version": "0.1.0",
                "engine_code_hash": engine_hash,
                "final_decision_hash": final_hash,
            }
        )
        self.final_record = {
            "final_decision_id": final_id,
            "candidate": copy.deepcopy(candidate),
            "candidate_dataset_hash": dataset_hash,
            "engine_version": "0.1.0",
            "engine_code_hash": engine_hash,
            "final_decision_hash": final_hash,
            "decision_commitment": decision_commitment,
            "run": run,
            "verification_mode": "LOCAL",
            "verification_label": "Demo local verification — not on-chain",
        }
        self.room_status = "COMPLETED"

    def receipt(self, participant: str) -> dict[str, Any]:
        self._participant(participant)
        if not self.final_record:
            raise DemoError(409, "NOT_READY", "최종 결정이 아직 없습니다.")
        record = self.final_record
        own = [
            item
            for item in record["run"]["frozen_constraints"]
            if item["participant_pseudonym"] == participant
        ]
        return {
            "participant_pseudonym": participant,
            "final_decision_id": record["final_decision_id"],
            "decision_run_id": record["run"]["decision_run_id"],
            "participant_inputs": [self._public_constraint(item) for item in own],
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

    def verify(self, participant: str) -> dict[str, Any]:
        receipt = self.receipt(participant)
        checks = {
            "input_set_root_matches": input_root(receipt["input_set_leaves"]) == receipt["input_set_root"],
            "candidate_dataset_hash_matches": hash_json(DEMO_CANDIDATES) == receipt["candidate_dataset_hash"],
            "engine_code_hash_matches": keccak256(Path(__file__).with_name("engine.py").read_bytes()) == receipt["engine_code_hash"],
        }
        return {
            "status": "VERIFIED" if all(checks.values()) else "INVALID",
            "verification_mode": "LOCAL",
            "verification_label": "Demo local verification — not on-chain",
            "checks": checks,
        }

    def _participant(self, participant: str) -> None:
        if participant not in self.participants:
            raise DemoError(404, "NOT_FOUND", "참가자를 찾을 수 없습니다.")

