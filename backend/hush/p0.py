"""Canonical multi-room P0 application service.

The original DemoService remains a stable presentation slice.  This module
implements the broader P0 contract: multiple durable rooms, dynamic rosters,
multiple constraint versions, explicit CONSTRAINED/EMPTY input confirmation,
frozen decision inputs, private proposals, and idempotent mutations.
"""

from __future__ import annotations

import copy
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from . import chain
from .crypto import condition_commitment, hash_json, input_leaf, input_root, keccak256
from .engine import decide
from .fixtures import DEMO_CANDIDATES
from .parser import ParseError, structure_constraint
from .service import DemoError, ENGINE_VERSION
from .store import StateStore

_CATEGORIES = {"seafood", "korean", "japanese", "chinese", "western", "meat", "vegetarian", "cafe"}
_FEATURES = {"wheelchair_ramp", "elevator", "accessible_restroom"}
_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class P0Service:
    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store or StateStore()
        self._lock = RLock()
        self.rooms: dict[str, dict[str, Any]] = {}
        self.creation_idempotency: dict[str, dict[str, Any]] = {}
        for room_id in self.store.list_room_ids():
            if room_id == "__p0_index__":
                saved = self.store.load(room_id) or {}
                self.creation_idempotency = saved.get("creation_idempotency", {})
                continue
            if room_id == "hush-demo-dinner-001":
                continue
            saved = self.store.load(room_id)
            if saved and saved.get("service") == "P0":
                self.rooms[room_id] = saved

    def _save(self, room: dict[str, Any]) -> None:
        self.store.save(room["decision_room_id"], room)

    def _save_index(self) -> None:
        self.store.save("__p0_index__", {
            "service": "P0_INDEX", "creation_idempotency": self.creation_idempotency
        })

    def _room(self, room_id: str) -> dict[str, Any]:
        room = self.rooms.get(room_id)
        if room is None:
            raise DemoError(404, "NOT_FOUND", "의사결정 방을 찾을 수 없습니다.")
        return room

    @staticmethod
    def _participant(room: dict[str, Any], session: str | None) -> dict[str, Any]:
        participant_id = room["sessions"].get(session or "")
        participant = room["participants"].get(participant_id or "")
        expired = False
        if participant and participant.get("session_expires_at"):
            expired = datetime.fromisoformat(participant["session_expires_at"]) <= datetime.now(timezone.utc)
        if not participant or participant["status"] == "REVOKED" or expired:
            raise DemoError(404, "NOT_FOUND", "참가자 전용 정보를 찾을 수 없습니다.")
        return participant

    @staticmethod
    def _require_creator(room: dict[str, Any], session: str | None) -> None:
        if not session or not secrets.compare_digest(session, room["creator_session"]):
            raise DemoError(404, "NOT_FOUND", "관리자 기능을 찾을 수 없습니다.")

    @staticmethod
    def _fingerprint(operation: str, body: Any) -> str:
        return hash_json({"operation": operation, "body": body})

    @staticmethod
    def _commitment_attempt(provenance: dict[str, Any]) -> dict[str, Any]:
        return {
            "commitment_attempt_id": "attempt-" + secrets.token_hex(8),
            "status": provenance.get("status", "FAILED"),
            "created_at": _now(),
            "chain_provenance": copy.deepcopy(provenance),
        }

    @staticmethod
    def _chain_unavailable(exc: Exception) -> dict[str, Any]:
        return {
            "status": "FAILED",
            "verification_mode": "ONCHAIN",
            "reason": str(exc)[:200],
            "transactions": [],
        }

    def _idempotent(
        self,
        room: dict[str, Any],
        key: str | None,
        operation: str,
        body: Any,
        mutation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if not key:
            raise DemoError(422, "VALIDATION_ERROR", "Idempotency-Key 헤더가 필요합니다.")
        fingerprint = self._fingerprint(operation, body)
        existing = room["idempotency"].get(key)
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise DemoError(409, "IDEMPOTENCY_KEY_REUSED", "같은 요청 키가 다른 내용에 사용됐습니다.")
            return copy.deepcopy(existing["response"])
        snapshot = copy.deepcopy(room)
        try:
            response = mutation()
            room["idempotency"][key] = {
                "fingerprint": fingerprint, "response": copy.deepcopy(response)
            }
            self._save(room)
        except DemoError:
            room.clear()
            room.update(snapshot)
            raise
        except Exception as exc:
            room.clear()
            room.update(snapshot)
            raise DemoError(
                503, "DEPENDENCY_UNAVAILABLE",
                "상태를 안전하게 저장하지 못했습니다. 같은 요청 키로 다시 시도해 주세요.",
            ) from exc
        return response

    def create_room(
        self, title: str, required_count: int, dataset_version: str, idem_key: str | None
    ) -> dict[str, Any]:
        if not idem_key:
            raise DemoError(422, "VALIDATION_ERROR", "Idempotency-Key 헤더가 필요합니다.")
        if dataset_version != "demo-candidates-v1":
            raise DemoError(422, "VALIDATION_ERROR", "지원하지 않는 후보 데이터 버전입니다.")
        if not 2 <= required_count <= 20:
            raise DemoError(422, "VALIDATION_ERROR", "참가자 수는 2명 이상 20명 이하여야 합니다.")
        with self._lock:
            fingerprint = self._fingerprint("create-room", {
                "title": title, "required_participant_count": required_count,
                "candidate_dataset_version": dataset_version,
            })
            existing = self.creation_idempotency.get(idem_key)
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise DemoError(409, "IDEMPOTENCY_KEY_REUSED", "같은 요청 키가 다른 내용에 사용됐습니다.")
                return copy.deepcopy(existing["response"])
            room_id = "room-" + secrets.token_hex(8)
            creator_session = secrets.token_urlsafe(32)
            invite_token = secrets.token_urlsafe(24)
            room = {
                "service": "P0",
                "decision_room_id": room_id,
                "title": title,
                "status": "OPEN",
                "required_participant_count": required_count,
                "candidate_dataset_version": dataset_version,
                "candidate_dataset_hash": hash_json(DEMO_CANDIDATES),
                "creator_session": creator_session,
                "invite_token": invite_token,
                "participants": {},
                "sessions": {},
                "private_inputs": {},
                "drafts": {},
                "constraints": [],
                "runs": [],
                "proposals": [],
                "approvals": [],
                "final_record": None,
                "idempotency": {},
                "created_at": _now(),
            }
            self.rooms[room_id] = room
            self._save(room)
            response = {
                "decision_room_id": room_id,
                "status": "OPEN",
                "required_participant_count": required_count,
                "candidate_dataset_hash": room["candidate_dataset_hash"],
                "creator_session": creator_session,
                "invite_token": invite_token,
            }
            self.creation_idempotency[idem_key] = {
                "fingerprint": fingerprint, "response": copy.deepcopy(response)
            }
            self._save_index()
            return response

    @staticmethod
    def _validate_constraint(body: dict[str, Any]) -> None:
        kind = body["constraint_type"]
        value = body["constraint_value"]
        try:
            if kind == "max_price":
                valid = (
                    set(value) == {"amount", "currency"}
                    and isinstance(value["amount"], int)
                    and 1 <= value["amount"] <= 10_000_000
                    and value["currency"] == "KRW"
                )
            elif kind == "excluded_category":
                valid = (
                    set(value) == {"categories"} and isinstance(value["categories"], list)
                    and bool(value["categories"])
                    and all(item in _CATEGORIES for item in value["categories"])
                )
            elif kind == "accessibility_required":
                valid = (
                    set(value) == {"features"} and isinstance(value["features"], list)
                    and bool(value["features"])
                    and all(item in _FEATURES for item in value["features"])
                )
            elif kind == "max_travel_minutes":
                valid = (
                    set(value) == {"minutes"} and isinstance(value["minutes"], int)
                    and 1 <= value["minutes"] <= 1440
                )
            else:
                valid = set(value) == {"time"} and bool(_TIME.fullmatch(value["time"]))
        except (KeyError, TypeError):
            valid = False
        if not valid:
            raise DemoError(422, "VALIDATION_ERROR", "조건 값이 P0 스키마와 맞지 않습니다.")

    def join(self, room_id: str, invite_token: str, idem_key: str | None) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            body = {"invite_token": invite_token}

            def mutation() -> dict[str, Any]:
                if room["status"] not in {"OPEN", "COLLECTING"}:
                    raise DemoError(409, "INVALID_STATE", "현재 방에는 참가할 수 없습니다.")
                if not secrets.compare_digest(invite_token, room["invite_token"]):
                    raise DemoError(404, "NOT_FOUND", "초대 정보를 확인할 수 없습니다.")
                active_count = sum(
                    item["status"] != "REVOKED" for item in room["participants"].values()
                )
                if active_count >= room["required_participant_count"]:
                    raise DemoError(409, "INVALID_STATE", "필요한 참가자가 모두 참여했습니다.")
                index = len(room["participants"])
                pseudonym = chr(ord("A") + index) if index < 26 else f"P{index + 1}"
                participant_id = "participant-" + secrets.token_hex(8)
                session = secrets.token_urlsafe(32)
                participant = {
                    "participant_id": participant_id,
                    "participant_pseudonym": pseudonym,
                    "status": "JOINED",
                    "input_status": "PENDING_INPUT",
                    "input_mode": None,
                    "joined_at": _now(),
                    "session_expires_at": (
                        datetime.now(timezone.utc) + timedelta(hours=24)
                    ).isoformat(),
                }
                room["participants"][participant_id] = participant
                room["sessions"][session] = participant_id
                room["status"] = "COLLECTING"
                return {**participant, "participant_session": session}

            return self._idempotent(room, idem_key, "join", body, mutation)

    def shared(self, room_id: str) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            result = {
                "decision_room_id": room_id,
                "title": room["title"],
                "status": room["status"],
                "required_participant_count": room["required_participant_count"],
                "participant_count": sum(
                    item["status"] != "REVOKED" for item in room["participants"].values()
                ),
                "input_confirmed_participant_count": sum(
                    item["input_status"] == "INPUT_CONFIRMED"
                    for item in room["participants"].values()
                ),
                "eligible_participant_count": sum(
                    item["status"] != "REVOKED" for item in room["participants"].values()
                ),
                "decision_status": room["status"],
            }
            if room["status"] == "NEGOTIATING":
                result["decision_status"] = "PRIVATE_ADJUSTMENT_AVAILABLE"
            if room["status"] == "COMPLETED" and room["final_record"]:
                result["final_decision"] = {
                    key: room["final_record"][key]
                    for key in ("final_decision_id", "candidate_id", "candidate_name", "decision_commitment")
                }
            return result

    def me(self, room_id: str, session: str | None) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._participant(self._room(room_id), session))

    def revoke_participant(
        self, room_id: str, creator_session: str | None, participant_id: str,
        idem_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            self._require_creator(room, creator_session)

            def mutation() -> dict[str, Any]:
                if room["status"] not in {"OPEN", "COLLECTING"}:
                    raise DemoError(409, "INVALID_STATE", "현재는 참가를 철회할 수 없습니다.")
                participant = room["participants"].get(participant_id)
                if participant is None:
                    raise DemoError(404, "NOT_FOUND", "참가자를 찾을 수 없습니다.")
                participant["status"] = "REVOKED"
                participant["input_status"] = "PENDING_INPUT"
                for token, owner in list(room["sessions"].items()):
                    if owner == participant_id:
                        del room["sessions"][token]
                return {"participant_id": participant_id, "status": "REVOKED"}

            return self._idempotent(
                room, idem_key, "revoke-participant", {"participant_id": participant_id}, mutation
            )

    def submit_private_input(
        self, room_id: str, session: str | None, source_text: str, idem_key: str | None
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)

            def mutation() -> dict[str, Any]:
                if room["status"] != "COLLECTING" or participant["input_status"] == "INPUT_CONFIRMED":
                    raise DemoError(409, "INVALID_STATE", "현재는 입력을 추가할 수 없습니다.")
                private_input_id = "input-" + secrets.token_hex(8)
                room["private_inputs"][private_input_id] = {
                    "private_input_id": private_input_id,
                    "participant_id": participant["participant_id"],
                    "source_text": source_text,
                    "status": "RECEIVED",
                }
                return {"private_input_id": private_input_id, "status": "RECEIVED"}

            return self._idempotent(room, idem_key, "private-input", {"source_text": source_text}, mutation)

    def parse_private_input(
        self, room_id: str, session: str | None, private_input_id: str, idem_key: str | None
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            item = room["private_inputs"].get(private_input_id)
            if not item or item["participant_id"] != participant["participant_id"]:
                raise DemoError(404, "NOT_FOUND", "비공개 입력을 찾을 수 없습니다.")

            def mutation() -> dict[str, Any]:
                try:
                    parsed = structure_constraint(item["source_text"])
                except ParseError as exc:
                    raise DemoError(422, "AI_PARSE_FAILED", str(exc)) from exc
                draft_id = "draft-" + secrets.token_hex(8)
                room["drafts"][draft_id] = {
                    "draft_id": draft_id,
                    "participant_id": participant["participant_id"],
                    "private_input_id": private_input_id,
                    **parsed,
                }
                item["status"] = "PARSED"
                return {"parse_id": draft_id, "status": "PARSED", "structured_candidates": [parsed["structured_candidate"]]}

            return self._idempotent(room, idem_key, "parse-input", {"private_input_id": private_input_id}, mutation)

    def drafts(self, room_id: str, session: str | None) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            return {
                "constraints": [
                    {"draft_id": item["draft_id"], **copy.deepcopy(item["structured_candidate"])}
                    for item in room["drafts"].values()
                    if item["participant_id"] == participant["participant_id"]
                ]
            }

    def confirm_constraint(
        self, room_id: str, session: str | None, body: dict[str, Any], idem_key: str | None
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)

            def mutation() -> dict[str, Any]:
                if room["status"] != "COLLECTING" or participant["input_status"] == "INPUT_CONFIRMED":
                    raise DemoError(409, "INVALID_STATE", "현재는 조건을 확정할 수 없습니다.")
                self._validate_constraint(body)
                constraint_id = "constraint-" + secrets.token_hex(8)
                version = {
                    "constraint_id": constraint_id,
                    "constraint_version_id": constraint_id + "-v1",
                    "participant_input_id": "participant-input-" + secrets.token_hex(8),
                    "constraint_version": 1,
                    "participant_id": participant["participant_id"],
                    "participant_pseudonym": participant["participant_pseudonym"],
                    "constraint_type": body["constraint_type"],
                    "priority": body["priority"],
                    "constraint_value": copy.deepcopy(body["constraint_value"]),
                    "source_text": body.get("source_text"),
                    "status": "ACTIVE",
                    "commitment_status": "LOCAL_CONFIRMED",
                    "salt": "0x" + secrets.token_hex(32),
                }
                payload = {
                    key: version[key]
                    for key in (
                        "decision_room_id",
                        "participant_pseudonym",
                        "constraint_id",
                        "constraint_version",
                        "constraint_type",
                        "priority",
                        "constraint_value",
                    )
                    if key in version
                }
                payload["decision_room_id"] = room_id
                version["condition_commitment"] = condition_commitment(payload, version["salt"])
                provenance = None
                if chain.chain_enabled():
                    version.update({"status": "PENDING_ACTIVATION", "commitment_status": "PENDING"})
                    try:
                        provenance = chain.commit_condition(
                            room_id=room_id,
                            participant_pseudonym=version["participant_pseudonym"],
                            constraint_version_id=version["constraint_version_id"],
                            constraint_version=version["constraint_version"],
                            condition_commitment=version["condition_commitment"],
                        )
                    except chain.ChainUnavailable as exc:
                        provenance = self._chain_unavailable(exc)
                    if provenance.get("status") == "CONFIRMED":
                        version.update({"status": "ACTIVE", "commitment_status": "CONFIRMED"})
                    else:
                        version["commitment_status"] = "FAILED"
                    version["chain_provenance"] = provenance
                    version["commitment_attempts"] = [self._commitment_attempt(provenance)]
                room["constraints"].append(version)
                response = {
                    key: version[key]
                    for key in (
                        "constraint_id",
                        "constraint_version_id",
                        "constraint_version",
                        "status",
                        "condition_commitment",
                        "commitment_status",
                    )
                }
                if provenance:
                    response["chain_provenance"] = copy.deepcopy(provenance)
                return response

            return self._idempotent(room, idem_key, "confirm-constraint", body, mutation)

    def constraints_me(self, room_id: str, session: str | None) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            return {
                "constraints": [
                    {key: copy.deepcopy(value) for key, value in item.items() if key != "salt"}
                    for item in room["constraints"]
                    if item["participant_id"] == participant["participant_id"]
                ]
            }

    def retry_constraint_commitment(
        self, room_id: str, session: str | None, version_id: str,
        idem_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            version = next((
                item for item in room["constraints"]
                if item["constraint_version_id"] == version_id
                and item["participant_id"] == participant["participant_id"]
            ), None)
            if version is None:
                raise DemoError(404, "NOT_FOUND", "조건을 찾을 수 없습니다.")

            def mutation() -> dict[str, Any]:
                if not chain.chain_enabled():
                    raise DemoError(409, "CHAIN_DISABLED", "온체인 기록 기능이 꺼져 있습니다.")
                if version["status"] != "PENDING_ACTIVATION" or version["commitment_status"] != "FAILED":
                    raise DemoError(409, "INVALID_STATE", "재시도할 수 있는 실패 상태가 아닙니다.")
                previous_id = version.get("supersedes_constraint_version_id")
                if previous_id:
                    previous = next((
                        item for item in room["constraints"]
                        if item["constraint_version_id"] == previous_id
                    ), None)
                    if previous is None:
                        raise DemoError(409, "INVALID_STATE", "이전 조건 버전을 찾을 수 없습니다.")
                    try:
                        provenance = chain.supersede_condition(
                            room_id=room_id,
                            participant_pseudonym=version["participant_pseudonym"],
                            previous_constraint_version_id=previous["constraint_version_id"],
                            previous_constraint_version=previous["constraint_version"],
                            previous_condition_commitment=previous["condition_commitment"],
                            new_constraint_version_id=version["constraint_version_id"],
                            new_constraint_version=version["constraint_version"],
                            new_condition_commitment=version["condition_commitment"],
                        )
                    except chain.ChainUnavailable as exc:
                        provenance = self._chain_unavailable(exc)
                else:
                    try:
                        provenance = chain.commit_condition(
                            room_id=room_id,
                            participant_pseudonym=version["participant_pseudonym"],
                            constraint_version_id=version["constraint_version_id"],
                            constraint_version=version["constraint_version"],
                            condition_commitment=version["condition_commitment"],
                        )
                    except chain.ChainUnavailable as exc:
                        provenance = self._chain_unavailable(exc)
                version["chain_provenance"] = provenance
                version.setdefault("commitment_attempts", []).append(
                    self._commitment_attempt(provenance)
                )
                if provenance.get("status") == "CONFIRMED":
                    version.update({"status": "ACTIVE", "commitment_status": "CONFIRMED"})
                    if previous_id:
                        previous["status"] = "SUPERSEDED"
                        room["status"] = "READY"
                else:
                    version["commitment_status"] = "FAILED"
                return {
                    "constraint_version_id": version_id,
                    "status": version["status"],
                    "commitment_status": version["commitment_status"],
                    "chain_provenance": copy.deepcopy(provenance),
                }

            return self._idempotent(
                room, idem_key, "retry-constraint-commitment",
                {"constraint_version_id": version_id}, mutation,
            )

    def retire_constraint(
        self, room_id: str, session: str | None, version_id: str,
        idem_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)

            def mutation() -> dict[str, Any]:
                if room["status"] != "COLLECTING" or participant["input_status"] == "INPUT_CONFIRMED":
                    raise DemoError(409, "INVALID_STATE", "입력 확정 전 활성 조건만 철회할 수 있습니다.")
                version = next((
                    item for item in room["constraints"]
                    if item["constraint_version_id"] == version_id
                    and item["participant_id"] == participant["participant_id"]
                ), None)
                if version is None:
                    raise DemoError(404, "NOT_FOUND", "조건을 찾을 수 없습니다.")
                if version["status"] != "ACTIVE":
                    raise DemoError(409, "STALE_CONSTRAINT_VERSION", "현재 활성 조건이 아닙니다.")
                version["status"] = "RETIRED"
                return {"constraint_version_id": version_id, "status": "RETIRED"}

            return self._idempotent(
                room, idem_key, "retire-constraint", {"constraint_version_id": version_id}, mutation
            )

    def confirm_input(
        self, room_id: str, session: str | None, mode: str, idem_key: str | None
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)

            def mutation() -> dict[str, Any]:
                own_active = [
                    item for item in room["constraints"]
                    if item["participant_id"] == participant["participant_id"] and item["status"] == "ACTIVE"
                ]
                if mode == "CONSTRAINED" and not own_active:
                    raise DemoError(409, "INVALID_STATE", "확정할 조건이 없습니다.")
                if mode == "EMPTY" and own_active:
                    raise DemoError(409, "INVALID_STATE", "조건이 있으면 EMPTY로 확정할 수 없습니다.")
                participant.update({"status": "ACTIVE", "input_status": "INPUT_CONFIRMED", "input_mode": mode})
                if mode == "EMPTY":
                    participant_input_id = "participant-input-" + secrets.token_hex(8)
                    empty_salt = "0x" + secrets.token_hex(32)
                    empty_payload = {
                        "decision_room_id": room_id,
                        "participant_pseudonym": participant["participant_pseudonym"],
                        "participant_input_id": participant_input_id,
                        "input_mode": "EMPTY",
                        "empty_marker": "HUSH_P0_EMPTY",
                    }
                    participant["empty_input"] = {
                        "participant_input_id": participant_input_id,
                        "condition_commitment": condition_commitment(empty_payload, empty_salt),
                        "empty_salt": empty_salt,
                        "condition_payload": empty_payload,
                    }
                if (
                    sum(item["status"] != "REVOKED" for item in room["participants"].values())
                    == room["required_participant_count"]
                    and all(
                        item["input_status"] == "INPUT_CONFIRMED"
                        for item in room["participants"].values()
                        if item["status"] != "REVOKED"
                    )
                ):
                    room["status"] = "READY"
                return {"input_status": "INPUT_CONFIRMED", "input_mode": mode}

            return self._idempotent(room, idem_key, "confirm-input", {"input_mode": mode}, mutation)

    def run_decision(self, room_id: str, session: str | None, idem_key: str | None) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            self._participant(room, session)

            def mutation() -> dict[str, Any]:
                if room["status"] != "READY":
                    raise DemoError(409, "INVALID_STATE", "결정을 실행할 준비가 되지 않았습니다.")
                run_id = "run-" + secrets.token_hex(8)
                active = [copy.deepcopy(item) for item in room["constraints"] if item["status"] == "ACTIVE"]
                entries: list[dict[str, Any]] = []
                for participant in sorted(
                    (item for item in room["participants"].values() if item["status"] != "REVOKED"),
                    key=lambda x: x["participant_pseudonym"],
                ):
                    own = [item for item in active if item["participant_id"] == participant["participant_id"]]
                    if participant["input_mode"] == "EMPTY":
                        own = [{
                            "constraint_version_id": None,
                            **copy.deepcopy(participant["empty_input"]),
                        }]
                    for item in own:
                        participant_input_id = item["participant_input_id"]
                        leaf_data = {
                            "decision_room_id": room_id,
                            "decision_run_id": run_id,
                            "participant_input_id": participant_input_id,
                            "input_mode": participant["input_mode"],
                            "constraint_version_id": item.get("constraint_version_id"),
                            "condition_commitment": item["condition_commitment"],
                        }
                        entries.append({
                            **leaf_data,
                            "participant_id": participant["participant_id"],
                            "participant_pseudonym": participant["participant_pseudonym"],
                            "constraint_id": item.get("constraint_id"),
                            "constraint_version": item.get("constraint_version"),
                            "input_set_leaf": input_leaf(leaf_data),
                            **({"empty_salt": item["empty_salt"]} if item.get("empty_salt") else {}),
                            **({"empty_condition_payload": item["condition_payload"]} if item.get("condition_payload") else {}),
                        })
                leaves = [item["input_set_leaf"] for item in entries]
                engine_result = decide(DEMO_CANDIDATES, active)
                run = {
                    "decision_run_id": run_id,
                    "status": engine_result.result_type,
                    "frozen_participant_inputs": entries,
                    "active_constraint_versions": active,
                    "input_set_leaves": sorted(leaves),
                    "input_set_root": input_root(leaves),
                    "engine_result": engine_result.__dict__,
                    "created_at": _now(),
                }
                room["runs"].append(run)
                if engine_result.result_type == "INFEASIBLE":
                    if engine_result.proposal is None:
                        room["status"] = "CLOSED"
                        return {"decision_run_id": run_id, "status": "INFEASIBLE", "decision_status": "NO_VALID_RELAXATION"}
                    target = next(item for item in active if item["constraint_id"] == engine_result.proposal["constraint_id"])
                    proposal = {
                        **copy.deepcopy(engine_result.proposal),
                        "relaxation_proposal_id": "proposal-" + secrets.token_hex(8),
                        "constraint_version_id": target["constraint_version_id"],
                        "status": "PROPOSED",
                        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    }
                    room["proposals"].append(proposal)
                    room["status"] = "NEGOTIATING"
                    return {"decision_run_id": run_id, "status": "INFEASIBLE", "result_type": "INFEASIBLE", "decision_status": "PRIVATE_ADJUSTMENT_AVAILABLE", "input_set_root": run["input_set_root"]}
                candidate = next(item for item in DEMO_CANDIDATES if item["candidate_id"] == engine_result.selected_candidate_id)
                engine_hash = keccak256(Path(__file__).with_name("engine.py").read_bytes())
                final_id = "final-" + secrets.token_hex(8)
                final_hash = hash_json({"final_decision_id": final_id, "candidate_id": candidate["candidate_id"], "input_set_root": run["input_set_root"], "candidate_dataset_hash": room["candidate_dataset_hash"], "engine_version": ENGINE_VERSION, "engine_code_hash": engine_hash})
                commitment = hash_json({"decision_room_id": room_id, "input_set_root": run["input_set_root"], "candidate_dataset_hash": room["candidate_dataset_hash"], "engine_version": ENGINE_VERSION, "engine_code_hash": engine_hash, "final_decision_hash": final_hash})
                provenance = None
                final_status = "COMMITTED_LOCALLY"
                if chain.chain_enabled():
                    room["status"] = "FINALIZING"
                    try:
                        provenance = chain.anchor_existing_decision(
                            room_id=room_id, input_set_root=run["input_set_root"],
                            candidate_dataset_hash=room["candidate_dataset_hash"],
                            engine_code_hash=engine_hash, final_decision_hash=final_hash,
                        )
                    except chain.ChainUnavailable as exc:
                        provenance = self._chain_unavailable(exc)
                    if provenance.get("status") == "CONFIRMED":
                        commitment = provenance["onchain_decision_commitment"]
                        final_status = "COMMITTED"
                    else:
                        final_status = "COMMITMENT_FAILED"
                room["final_record"] = {"final_decision_id": final_id, "candidate_id": candidate["candidate_id"], "candidate_name": candidate["name"], "candidate": candidate, "decision_commitment": commitment, "final_decision_hash": final_hash, "engine_code_hash": engine_hash, "run": run, "status": final_status, "chain_provenance": provenance}
                if provenance:
                    room["final_record"]["commitment_attempts"] = [
                        self._commitment_attempt(provenance)
                    ]
                room["status"] = "COMPLETED" if final_status != "COMMITMENT_FAILED" else "FINALIZING"
                if room["status"] == "COMPLETED":
                    for item in room["participants"].values():
                        if item["status"] != "REVOKED":
                            item["status"] = "RECEIPT_AVAILABLE"
                return {"decision_run_id": run_id, "status": "FEASIBLE", "result_type": "FEASIBLE", "selected_candidate_id": candidate["candidate_id"], "decision_status": room["status"], "input_set_root": run["input_set_root"], "commitment_status": final_status}

            return self._idempotent(room, idem_key, "decision-run", {}, mutation)

    def proposals_me(self, room_id: str, session: str | None) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            return {"proposals": [copy.deepcopy(item) for item in room["proposals"] if item["participant_pseudonym"] == participant["participant_pseudonym"]]}

    def decide_proposal(
        self, room_id: str, session: str | None, proposal_id: str,
        constraint_version_id: str, decision: str, idem_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            proposal = next((item for item in room["proposals"] if item["relaxation_proposal_id"] == proposal_id), None)
            if not proposal or proposal["participant_pseudonym"] != participant["participant_pseudonym"]:
                raise DemoError(404, "NOT_FOUND", "협상안을 찾을 수 없습니다.")
            if (
                proposal["status"] == "PROPOSED"
                and datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(timezone.utc)
            ):
                proposal["status"] = "EXPIRED"
                self._save(room)
                raise DemoError(409, "INVALID_STATE", "협상안이 만료되었습니다.")
            body = {"constraint_version_id": constraint_version_id, "decision": decision}

            def mutation() -> dict[str, Any]:
                if proposal["status"] != "PROPOSED":
                    raise DemoError(409, "INVALID_STATE", "이미 처리된 협상안입니다.")
                if proposal["constraint_version_id"] != constraint_version_id:
                    raise DemoError(409, "STALE_CONSTRAINT_VERSION", "조건 버전이 오래되었습니다.")
                approval = {"user_approval_id": "approval-" + secrets.token_hex(8), "decision": decision, "created_at": _now()}
                room["approvals"].append(approval)
                proposal["status"] = decision
                if decision == "REJECTED":
                    room["status"] = "CLOSED"
                    return {**approval, "status": "REJECTED"}
                old = next((item for item in room["constraints"] if item["constraint_version_id"] == constraint_version_id and item["status"] == "ACTIVE"), None)
                if old is None:
                    raise DemoError(409, "STALE_CONSTRAINT_VERSION", "현재 활성 조건이 아닙니다.")
                successor = copy.deepcopy(old)
                successor.update({"constraint_version_id": old["constraint_id"] + f"-v{old['constraint_version'] + 1}", "participant_input_id": "participant-input-" + secrets.token_hex(8), "constraint_version": old["constraint_version"] + 1, "constraint_value": copy.deepcopy(proposal["proposed_constraint_value"]), "status": "ACTIVE", "commitment_status": "LOCAL_CONFIRMED", "salt": "0x" + secrets.token_hex(32), "supersedes_constraint_version_id": old["constraint_version_id"]})
                payload = {"decision_room_id": room_id, "participant_pseudonym": successor["participant_pseudonym"], "constraint_id": successor["constraint_id"], "constraint_version": successor["constraint_version"], "constraint_type": successor["constraint_type"], "priority": successor["priority"], "constraint_value": successor["constraint_value"]}
                successor["condition_commitment"] = condition_commitment(payload, successor["salt"])
                provenance = None
                if chain.chain_enabled():
                    successor.update({"status": "PENDING_ACTIVATION", "commitment_status": "PENDING"})
                    try:
                        provenance = chain.supersede_condition(
                            room_id=room_id,
                            participant_pseudonym=successor["participant_pseudonym"],
                            previous_constraint_version_id=old["constraint_version_id"],
                            previous_constraint_version=old["constraint_version"],
                            previous_condition_commitment=old["condition_commitment"],
                            new_constraint_version_id=successor["constraint_version_id"],
                            new_constraint_version=successor["constraint_version"],
                            new_condition_commitment=successor["condition_commitment"],
                        )
                    except chain.ChainUnavailable as exc:
                        provenance = self._chain_unavailable(exc)
                    successor["chain_provenance"] = provenance
                    successor["commitment_attempts"] = [
                        self._commitment_attempt(provenance)
                    ]
                    if provenance.get("status") == "CONFIRMED":
                        successor.update({"status": "ACTIVE", "commitment_status": "CONFIRMED"})
                    else:
                        successor["commitment_status"] = "FAILED"
                room["constraints"].append(successor)
                if successor["status"] == "ACTIVE":
                    old["status"] = "SUPERSEDED"
                    room["status"] = "READY"
                else:
                    room["status"] = "NEGOTIATING"
                response = {**approval, "new_constraint_version_id": successor["constraint_version_id"], "constraint_version": successor["constraint_version"], "condition_commitment": successor["condition_commitment"], "commitment_status": successor["commitment_status"]}
                if provenance:
                    response["chain_provenance"] = copy.deepcopy(provenance)
                return response

            return self._idempotent(room, idem_key, f"proposal-{decision.lower()}", body, mutation)

    def retry_final_commitment(
        self, room_id: str, session: str | None, idem_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            self._participant(room, session)

            def mutation() -> dict[str, Any]:
                final = room.get("final_record")
                if not final or final["status"] != "COMMITMENT_FAILED":
                    raise DemoError(409, "INVALID_STATE", "재시도할 최종 기록 실패가 없습니다.")
                if not chain.chain_enabled():
                    raise DemoError(409, "CHAIN_DISABLED", "온체인 기록 기능이 꺼져 있습니다.")
                run = final["run"]
                try:
                    provenance = chain.anchor_existing_decision(
                        room_id=room_id,
                        input_set_root=run["input_set_root"],
                        candidate_dataset_hash=room["candidate_dataset_hash"],
                        engine_code_hash=final["engine_code_hash"],
                        final_decision_hash=final["final_decision_hash"],
                    )
                except chain.ChainUnavailable as exc:
                    provenance = self._chain_unavailable(exc)
                final["chain_provenance"] = provenance
                final.setdefault("commitment_attempts", []).append(
                    self._commitment_attempt(provenance)
                )
                if provenance.get("status") == "CONFIRMED":
                    final["status"] = "COMMITTED"
                    final["decision_commitment"] = provenance["onchain_decision_commitment"]
                    room["status"] = "COMPLETED"
                    for item in room["participants"].values():
                        if item["status"] != "REVOKED":
                            item["status"] = "RECEIPT_AVAILABLE"
                return {
                    "final_decision_id": final["final_decision_id"],
                    "decision_status": room["status"],
                    "commitment_status": final["status"],
                    "chain_provenance": copy.deepcopy(provenance),
                }

            return self._idempotent(room, idem_key, "retry-final-commitment", {}, mutation)

    def decision_run(self, room_id: str, run_id: str) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            run = next((item for item in room["runs"] if item["decision_run_id"] == run_id), None)
            if run is None:
                raise DemoError(404, "NOT_FOUND", "의사결정 실행 기록을 찾을 수 없습니다.")
            result = run["engine_result"]
            return {
                "decision_run_id": run_id,
                "status": run["status"],
                "result_type": result["result_type"],
                "feasible_candidate_count": len(result["feasible_candidate_ids"]),
                "decision_status": (
                    "PRIVATE_ADJUSTMENT_AVAILABLE"
                    if result["result_type"] == "INFEASIBLE" and result.get("proposal")
                    else run["status"]
                ),
            }

    def final_decision(self, room_id: str) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            if room["status"] != "COMPLETED" or not room["final_record"]:
                raise DemoError(409, "NOT_READY", "최종 결정이 아직 없습니다.")
            final = room["final_record"]
            return {
                "final_decision_id": final["final_decision_id"],
                "candidate_id": final["candidate_id"],
                "candidate_name": final["candidate_name"],
                "decision_commitment": final["decision_commitment"],
                "status": final["status"],
            }

    @staticmethod
    def _condition_payload(room_id: str, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision_room_id": room_id,
            "participant_pseudonym": item["participant_pseudonym"],
            "constraint_id": item["constraint_id"],
            "constraint_version": item["constraint_version"],
            "constraint_type": item["constraint_type"],
            "priority": item["priority"],
            "constraint_value": item["constraint_value"],
        }

    def receipt(self, room_id: str, session: str | None, include_private: bool = False) -> dict[str, Any]:
        with self._lock:
            room = self._room(room_id)
            participant = self._participant(room, session)
            final = room.get("final_record")
            if (
                not final
                or room["status"] != "COMPLETED"
                or final["status"] not in {"COMMITTED", "COMMITTED_LOCALLY"}
            ):
                raise DemoError(409, "NOT_READY", "최종 결정이 아직 없습니다.")
            run = final["run"]
            own_entries = [
                copy.deepcopy(item) for item in run["frozen_participant_inputs"]
                if item["participant_id"] == participant["participant_id"]
            ]
            public_entries = [
                {key: value for key, value in item.items() if key not in {
                    "participant_id", "participant_pseudonym", "empty_salt",
                    "empty_condition_payload",
                }} for item in own_entries
            ]
            for entry in public_entries:
                if entry["input_mode"] == "EMPTY":
                    for key in ("constraint_id", "constraint_version_id", "constraint_version"):
                        entry.pop(key, None)
            receipt = {
                "participant_receipt_id": "receipt-" + final["final_decision_id"] + "-" + participant["participant_id"],
                "participant_id": participant["participant_id"],
                "decision_room_id": room_id,
                "decision_run_id": run["decision_run_id"],
                "final_decision_id": final["final_decision_id"],
                "participant_inputs": public_entries,
                "input_set_leaves": run["input_set_leaves"],
                "input_set_root": run["input_set_root"],
                "candidate_dataset_hash": room["candidate_dataset_hash"],
                "engine_version": ENGINE_VERSION,
                "engine_code_hash": final["engine_code_hash"],
                "final_decision_hash": final["final_decision_hash"],
                "decision_commitment": final["decision_commitment"],
                "candidate": copy.deepcopy(final["candidate"]),
                "verification_mode": "LOCAL",
            }
            if final.get("chain_provenance"):
                receipt["chain_provenance"] = copy.deepcopy(final["chain_provenance"])
                if final["chain_provenance"].get("status") == "CONFIRMED":
                    receipt["verification_mode"] = "ONCHAIN"
            if include_private:
                frozen_versions = {
                    item["constraint_version_id"]: item for item in run["active_constraint_versions"]
                }
                materials = []
                for entry in own_entries:
                    version_id = entry.get("constraint_version_id")
                    if entry["input_mode"] == "EMPTY":
                        payload = entry["empty_condition_payload"]
                        salt = entry["empty_salt"]
                    else:
                        version = frozen_versions[version_id]
                        payload = self._condition_payload(room_id, version)
                        salt = version["salt"]
                    materials.append({
                        "constraint_version_id": version_id,
                        "condition_payload": payload,
                        "salt": salt,
                    })
                receipt["private_verification_material"] = materials
            return receipt

    def verify(self, room_id: str, session: str | None) -> dict[str, Any]:
        receipt = self.receipt(room_id, session, include_private=True)
        checks: dict[str, bool] = {}
        try:
            checks["input_set_root_matches"] = input_root(receipt["input_set_leaves"]) == receipt["input_set_root"]
            checks["candidate_dataset_hash_matches"] = hash_json(DEMO_CANDIDATES) == receipt["candidate_dataset_hash"]
            checks["engine_code_hash_matches"] = keccak256(Path(__file__).with_name("engine.py").read_bytes()) == receipt["engine_code_hash"]
            candidates = {item["candidate_id"]: item for item in DEMO_CANDIDATES}
            checks["candidate_matches_dataset"] = candidates.get(receipt["candidate"]["candidate_id"]) == receipt["candidate"]
            materials = {
                item["constraint_version_id"]: item for item in receipt["private_verification_material"]
            }
            commitments_ok = leaves_ok = included = bool(receipt["participant_inputs"])
            for entry in receipt["participant_inputs"]:
                material = materials.get(entry.get("constraint_version_id"))
                commitments_ok &= bool(material) and condition_commitment(
                    material["condition_payload"], material["salt"]
                ) == entry["condition_commitment"]
                leaf_data = {
                    "decision_room_id": entry["decision_room_id"],
                    "decision_run_id": entry["decision_run_id"],
                    "participant_input_id": entry["participant_input_id"],
                    "input_mode": entry["input_mode"],
                    "constraint_version_id": entry.get("constraint_version_id"),
                    "condition_commitment": entry["condition_commitment"],
                }
                leaves_ok &= input_leaf(leaf_data) == entry["input_set_leaf"]
                included &= entry["input_set_leaf"] in receipt["input_set_leaves"]
            checks["own_condition_commitment_matches"] = commitments_ok
            checks["own_input_leaf_matches"] = leaves_ok
            checks["own_input_included"] = included
            expected_final = hash_json({
                "final_decision_id": receipt["final_decision_id"],
                "candidate_id": receipt["candidate"]["candidate_id"],
                "input_set_root": receipt["input_set_root"],
                "candidate_dataset_hash": receipt["candidate_dataset_hash"],
                "engine_version": receipt["engine_version"],
                "engine_code_hash": receipt["engine_code_hash"],
            })
            checks["final_decision_hash_matches"] = expected_final == receipt["final_decision_hash"]
            provenance = receipt.get("chain_provenance") or {}
            if provenance.get("status") == "CONFIRMED":
                expected_commitment = provenance.get("onchain_decision_commitment")
            else:
                expected_commitment = hash_json({
                    "decision_room_id": room_id,
                    "input_set_root": receipt["input_set_root"],
                    "candidate_dataset_hash": receipt["candidate_dataset_hash"],
                    "engine_version": receipt["engine_version"],
                    "engine_code_hash": receipt["engine_code_hash"],
                    "final_decision_hash": receipt["final_decision_hash"],
                })
            checks["decision_commitment_matches"] = expected_commitment == receipt["decision_commitment"]
            if provenance.get("status") == "CONFIRMED":
                record = chain.read_decision_record(provenance["decision_room_key"])
                checks.update({
                    "onchain_decision_committed": record.get("decision_committed") is True,
                    "onchain_input_set_root_matches": str(record.get("input_set_root", "")).lower() == receipt["input_set_root"].lower(),
                    "onchain_candidate_dataset_hash_matches": str(record.get("candidate_dataset_hash", "")).lower() == receipt["candidate_dataset_hash"].lower(),
                    "onchain_engine_code_hash_matches": str(record.get("engine_code_hash", "")).lower() == receipt["engine_code_hash"].lower(),
                    "onchain_final_decision_hash_matches": str(record.get("final_decision_hash", "")).lower() == receipt["final_decision_hash"].lower(),
                    "onchain_decision_commitment_matches": str(record.get("decision_commitment", "")).lower() == receipt["decision_commitment"].lower(),
                })
                constrained = [
                    item for item in receipt["participant_inputs"]
                    if item["input_mode"] == "CONSTRAINED"
                ]
                condition_records_match = True
                expected_room_key = chain.canonical_room_key(room_id).lower()
                for entry in constrained:
                    condition_record = chain.read_condition_record(entry["constraint_version_id"])
                    condition_records_match &= (
                        condition_record.get("exists") is True
                        and str(condition_record.get("decision_room_key", "")).lower() == expected_room_key
                        and condition_record.get("constraint_version") == entry["constraint_version"]
                        and str(condition_record.get("condition_commitment", "")).lower()
                        == entry["condition_commitment"].lower()
                    )
                checks["onchain_own_condition_records_match"] = condition_records_match
        except chain.ChainUnavailable:
            return {
                "status": "UNAVAILABLE",
                "checks": checks,
                "verification_mode": receipt["verification_mode"],
                "message": "공개 블록체인 기록을 현재 조회할 수 없습니다. 잠시 후 다시 검증해 주세요.",
            }
        except (KeyError, TypeError, ValueError):
            checks = {"receipt_well_formed": False}
        return {"status": "VERIFIED" if all(checks.values()) else "INVALID", "checks": checks, "verification_mode": receipt["verification_mode"]}
