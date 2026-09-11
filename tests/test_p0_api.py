import itertools

import pytest
from fastapi.testclient import TestClient

from hush.main import app
from hush import chain
from hush.p0 import P0Service
from hush.service import DemoError
from hush.store import StateStore


client = TestClient(app)
counter = itertools.count(1)


def idem(label: str) -> dict[str, str]:
    return {"Idempotency-Key": f"{label}-{next(counter)}"}


def create_room(count: int = 2):
    headers = idem("create")
    body = {
        "title": "P0 통합 테스트",
        "required_participant_count": count,
        "candidate_dataset_version": "demo-candidates-v1",
    }
    response = client.post("/rooms", json=body, headers=headers)
    assert response.status_code == 201, response.text
    # Room creation is durable-idempotent too.
    assert client.post("/rooms", json=body, headers=headers).json() == response.json()
    return response.json()


def join(room: dict, label: str):
    response = client.post(
        f"/rooms/{room['decision_room_id']}/participants",
        json={"invite_token": room["invite_token"]},
        headers=idem(f"join-{label}"),
    )
    assert response.status_code == 201, response.text
    return response.json(), {"X-Participant-Session": response.json()["participant_session"]}


def add_constraint(room_id: str, session: dict, body: dict):
    response = client.post(
        f"/rooms/{room_id}/constraints", json=body,
        headers={**session, **idem("constraint")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_input(room_id: str, session: dict, mode: str):
    response = client.post(
        f"/rooms/{room_id}/input-confirmations",
        json={"input_mode": mode}, headers={**session, **idem("confirm-input")},
    )
    assert response.status_code == 200, response.text


def test_multi_room_isolation_multiple_constraints_and_empty_input():
    first = create_room()
    second = create_room()
    assert first["decision_room_id"] != second["decision_room_id"]

    a, a_session = join(first, "a")
    b, b_session = join(first, "b")
    assert (a["participant_pseudonym"], b["participant_pseudonym"]) == ("A", "B")

    add_constraint(first["decision_room_id"], a_session, {
        "constraint_type": "max_price", "priority": "HARD",
        "constraint_value": {"amount": 20000, "currency": "KRW"},
    })
    add_constraint(first["decision_room_id"], a_session, {
        "constraint_type": "latest_end_time", "priority": "HARD",
        "constraint_value": {"time": "21:00"},
    })
    assert len(client.get(
        f"/rooms/{first['decision_room_id']}/constraints/me", headers=a_session
    ).json()["constraints"]) == 2

    confirm_input(first["decision_room_id"], a_session, "CONSTRAINED")
    confirm_input(first["decision_room_id"], b_session, "EMPTY")
    shared = client.get(f"/rooms/{first['decision_room_id']}").json()
    assert shared["status"] == "READY"
    assert "participants" not in shared
    assert "constraints" not in shared

    run = client.post(
        f"/rooms/{first['decision_room_id']}/decision-runs",
        headers={**a_session, **idem("run")},
    )
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "FEASIBLE"
    run_id = run.json()["decision_run_id"]
    assert client.get(f"/rooms/{first['decision_room_id']}/decision-runs/{run_id}").json()["result_type"] == "FEASIBLE"
    assert client.get(f"/rooms/{first['decision_room_id']}/final-decision").status_code == 200
    for session in (a_session, b_session):
        receipt = client.get(
            f"/rooms/{first['decision_room_id']}/receipts/me", headers=session
        ).json()
        assert receipt["participant_inputs"]
        assert "private_verification_material" not in receipt
        verified = client.post(
            f"/rooms/{first['decision_room_id']}/verify", headers=session
        ).json()
        assert verified["status"] == "VERIFIED"
        assert all(verified["checks"].values())
        verification_data = client.get(
            f"/rooms/{first['decision_room_id']}/verification-data/me", headers=session
        ).json()
        serialized = str(verification_data)
        assert "private_verification_material" not in verification_data
        assert "empty_salt" not in serialized and "source_text" not in serialized
    assert client.get(f"/rooms/{second['decision_room_id']}").json()["status"] == "OPEN"


def test_idempotency_owner_isolation_and_stale_proposal_protection():
    room = create_room(4)
    joined = [join(room, str(i)) for i in range(4)]
    room_id = room["decision_room_id"]
    bodies = [
        {"constraint_type": "max_price", "priority": "HARD", "constraint_value": {"amount": 15000, "currency": "KRW"}},
        {"constraint_type": "excluded_category", "priority": "SOFT", "constraint_value": {"categories": ["seafood"]}},
        {"constraint_type": "accessibility_required", "priority": "HARD", "constraint_value": {"features": ["wheelchair_ramp"]}},
        {"constraint_type": "latest_end_time", "priority": "HARD", "constraint_value": {"time": "21:00"}},
    ]
    versions = []
    for (_, session), body in zip(joined, bodies):
        versions.append(add_constraint(room_id, session, body))
        confirm_input(room_id, session, "CONSTRAINED")

    run_headers = {**joined[0][1], **idem("run")}
    first = client.post(f"/rooms/{room_id}/decision-runs", headers=run_headers)
    assert first.json()["status"] == "INFEASIBLE"
    assert client.post(f"/rooms/{room_id}/decision-runs", headers=run_headers).json() == first.json()
    proposals = client.get(
        f"/rooms/{room_id}/relaxation-proposals/me", headers=joined[0][1]
    ).json()["proposals"]
    assert len(proposals) == 1
    assert client.get(
        f"/rooms/{room_id}/relaxation-proposals/me", headers=joined[1][1]
    ).json()["proposals"] == []

    proposal = proposals[0]
    wrong = client.post(
        f"/rooms/{room_id}/relaxation-proposals/{proposal['relaxation_proposal_id']}/accept",
        json={"constraint_version_id": "constraint-stale-v0"},
        headers={**joined[0][1], **idem("stale")},
    )
    assert wrong.status_code == 409
    assert wrong.json()["code"] == "STALE_CONSTRAINT_VERSION"

    accepted = client.post(
        f"/rooms/{room_id}/relaxation-proposals/{proposal['relaxation_proposal_id']}/accept",
        json={"constraint_version_id": versions[0]["constraint_version_id"]},
        headers={**joined[0][1], **idem("accept")},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["decision"] == "ACCEPTED"
    final = client.post(
        f"/rooms/{room_id}/decision-runs", headers={**joined[0][1], **idem("final-run")}
    )
    assert final.json()["selected_candidate_id"] == "restaurant-04"


def test_mutation_requires_idempotency_key_and_validates_constraint_shape():
    missing = client.post("/rooms", json={
        "title": "missing key", "required_participant_count": 2,
        "candidate_dataset_version": "demo-candidates-v1",
    })
    assert missing.status_code == 422
    assert missing.json()["code"] == "VALIDATION_ERROR"

    room = create_room()
    _, session = join(room, "a")
    invalid = client.post(
        f"/rooms/{room['decision_room_id']}/constraints",
        json={"constraint_type": "max_price", "priority": "HARD", "constraint_value": {"amount": -1, "currency": "KRW"}},
        headers={**session, **idem("invalid")},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"
    assert invalid.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in invalid.headers["Content-Security-Policy"]


def test_p0_frontend_surfaces_and_cross_owner_private_input_protection():
    for path, marker in (("/p0", "FULL P0 PARTICIPANT"), ("/p0-room", "SAFE PROJECTION"), ("/p0-verify", "INDEPENDENT VERIFICATION")):
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text

    room = create_room()
    _, a_session = join(room, "private-a")
    _, b_session = join(room, "private-b")
    received = client.post(
        f"/rooms/{room['decision_room_id']}/private-inputs",
        json={"source_text": "2만원 이하로 가고 싶어요"},
        headers={**a_session, **idem("private-input")},
    ).json()
    stolen = client.post(
        f"/rooms/{room['decision_room_id']}/private-inputs/{received['private_input_id']}/parse",
        headers={**b_session, **idem("cross-owner-parse")},
    )
    assert stolen.status_code == 404
    assert received["private_input_id"] not in str(
        client.get(f"/rooms/{room['decision_room_id']}").json()
    )

    parsed = client.post(
        f"/rooms/{room['decision_room_id']}/private-inputs/{received['private_input_id']}/parse",
        headers={**a_session, **idem("owner-parse")},
    )
    assert parsed.status_code == 200
    assert parsed.json()["parser_mode"] in {"LLM", "DEMO_RULE_PARSER"}
    assert isinstance(parsed.json()["is_ai"], bool)


def test_full_p0_chain_lifecycle_and_public_read_verification(monkeypatch):
    monkeypatch.setattr(chain, "chain_enabled", lambda: True)
    monkeypatch.setattr(chain, "commit_condition", lambda **kwargs: {
        "status": "CONFIRMED", "verification_mode": "ONCHAIN",
        "decision_room_key": "0x" + "11" * 32, "transactions": [],
    })
    monkeypatch.setattr(chain, "supersede_condition", lambda **kwargs: {
        "status": "CONFIRMED", "verification_mode": "ONCHAIN",
        "decision_room_key": "0x" + "11" * 32, "transactions": [],
    })
    room = create_room(4)
    joined = [join(room, f"chain-{i}") for i in range(4)]
    room_id = room["decision_room_id"]
    bodies = [
        {"constraint_type": "max_price", "priority": "HARD", "constraint_value": {"amount": 15000, "currency": "KRW"}},
        {"constraint_type": "excluded_category", "priority": "SOFT", "constraint_value": {"categories": ["seafood"]}},
        {"constraint_type": "accessibility_required", "priority": "HARD", "constraint_value": {"features": ["wheelchair_ramp"]}},
        {"constraint_type": "latest_end_time", "priority": "HARD", "constraint_value": {"time": "21:00"}},
    ]
    versions = []
    for (_, session), body in zip(joined, bodies):
        version = add_constraint(room_id, session, body)
        assert version["commitment_status"] == "CONFIRMED"
        versions.append(version)
        confirm_input(room_id, session, "CONSTRAINED")
    first = client.post(
        f"/rooms/{room_id}/decision-runs", headers={**joined[0][1], **idem("chain-run")}
    ).json()
    proposal = client.get(
        f"/rooms/{room_id}/relaxation-proposals/me", headers=joined[0][1]
    ).json()["proposals"][0]
    accepted = client.post(
        f"/rooms/{room_id}/relaxation-proposals/{proposal['relaxation_proposal_id']}/accept",
        json={"constraint_version_id": versions[0]["constraint_version_id"]},
        headers={**joined[0][1], **idem("chain-accept")},
    ).json()
    assert accepted["commitment_status"] == "CONFIRMED"

    commitment = "0x" + "aa" * 32
    monkeypatch.setattr(chain, "anchor_existing_decision", lambda **kwargs: {
        "status": "CONFIRMED", "verification_mode": "ONCHAIN",
        "decision_room_key": "0x" + "11" * 32,
        "onchain_decision_commitment": commitment, "transactions": [],
    })
    final = client.post(
        f"/rooms/{room_id}/decision-runs", headers={**joined[0][1], **idem("chain-final")}
    ).json()
    assert final["commitment_status"] == "COMMITTED"
    receipt = client.get(f"/rooms/{room_id}/receipts/me", headers=joined[0][1]).json()
    monkeypatch.setattr(chain, "read_decision_record", lambda _key: {
        "decision_committed": True,
        "input_set_root": receipt["input_set_root"],
        "candidate_dataset_hash": receipt["candidate_dataset_hash"],
        "engine_code_hash": receipt["engine_code_hash"],
        "final_decision_hash": receipt["final_decision_hash"],
        "decision_commitment": commitment,
    })
    monkeypatch.setattr(chain, "canonical_room_key", lambda _room_id: "0x" + "11" * 32)
    commitments = {item["constraint_version_id"]: item for item in client.get(
        f"/rooms/{room_id}/receipts/me", headers=joined[0][1]
    ).json()["participant_inputs"]}
    monkeypatch.setattr(chain, "read_condition_record", lambda version_id: {
        "exists": True,
        "decision_room_key": "0x" + "11" * 32,
        "constraint_version": commitments[version_id]["constraint_version"],
        "condition_commitment": commitments[version_id]["condition_commitment"],
    })
    verified = client.post(f"/rooms/{room_id}/verify", headers=joined[0][1]).json()
    assert verified["status"] == "VERIFIED"
    assert verified["verification_mode"] == "ONCHAIN"
    assert all(verified["checks"].values())


def test_constraint_retirement_participant_revocation_and_request_id():
    room = create_room()
    participant, session = join(room, "retire")
    version = add_constraint(room["decision_room_id"], session, {
        "constraint_type": "max_price", "priority": "HARD",
        "constraint_value": {"amount": 20000, "currency": "KRW"},
    })
    retired = client.post(
        f"/rooms/{room['decision_room_id']}/constraints/{version['constraint_version_id']}/retire",
        headers={**session, **idem("retire")},
    )
    assert retired.json()["status"] == "RETIRED"

    forbidden = client.post(
        f"/rooms/{room['decision_room_id']}/participants/{participant['participant_id']}/revoke",
        headers={**idem("revoke-no-owner"), "X-Creator-Session": "wrong"},
    )
    assert forbidden.status_code == 404
    assert forbidden.json()["request_id"] == forbidden.headers["X-Request-ID"]

    revoked = client.post(
        f"/rooms/{room['decision_room_id']}/participants/{participant['participant_id']}/revoke",
        headers={**idem("revoke"), "X-Creator-Session": room["creator_session"]},
    )
    assert revoked.json()["status"] == "REVOKED"
    assert client.get(
        f"/rooms/{room['decision_room_id']}/participants/me", headers=session
    ).status_code == 404
    replacement, _ = join(room, "replacement")
    assert replacement["participant_pseudonym"] != participant["participant_pseudonym"]


def test_p0_rooms_and_creation_idempotency_survive_restart(tmp_path):
    store = StateStore(f"sqlite:///{tmp_path / 'p0.db'}")
    first = P0Service(store)
    created = first.create_room("재시작 복구", 2, "demo-candidates-v1", "create-restart")
    joined = first.join(created["decision_room_id"], created["invite_token"], "join-restart")

    restarted = P0Service(StateStore(f"sqlite:///{tmp_path / 'p0.db'}"))
    assert restarted.create_room(
        "재시작 복구", 2, "demo-candidates-v1", "create-restart"
    ) == created
    assert restarted.shared(created["decision_room_id"])["participant_count"] == 1
    assert restarted.me(created["decision_room_id"], joined["participant_session"])[
        "participant_pseudonym"
    ] == "A"


def test_failed_database_save_rolls_back_in_memory_mutation(tmp_path, monkeypatch):
    service = P0Service(StateStore(f"sqlite:///{tmp_path / 'rollback.db'}"))
    room = service.create_room("rollback", 2, "demo-candidates-v1", "create")
    monkeypatch.setattr(service, "_save", lambda _room: (_ for _ in ()).throw(RuntimeError("db down")))
    with pytest.raises(DemoError) as error:
        service.join(room["decision_room_id"], room["invite_token"], "join")
    assert error.value.code == "DEPENDENCY_UNAVAILABLE"
    assert service.shared(room["decision_room_id"])["participant_count"] == 0


def test_failed_condition_commitment_can_be_retried(monkeypatch):
    monkeypatch.setattr(chain, "chain_enabled", lambda: True)
    attempts = itertools.count()

    def commit(**_kwargs):
        if next(attempts) == 0:
            return {"status": "FAILED", "verification_mode": "ONCHAIN", "transactions": []}
        return {
            "status": "CONFIRMED", "verification_mode": "ONCHAIN",
            "decision_room_key": "0x" + "12" * 32, "transactions": [],
        }

    monkeypatch.setattr(chain, "commit_condition", commit)
    room = create_room()
    _, session = join(room, "retry-condition")
    failed = add_constraint(room["decision_room_id"], session, {
        "constraint_type": "max_price", "priority": "HARD",
        "constraint_value": {"amount": 20000, "currency": "KRW"},
    })
    assert failed["status"] == "PENDING_ACTIVATION"
    assert failed["commitment_status"] == "FAILED"
    before = client.get(
        f"/rooms/{room['decision_room_id']}/constraints/me", headers=session
    ).json()["constraints"][0]
    assert len(before["commitment_attempts"]) == 1

    retried = client.post(
        f"/rooms/{room['decision_room_id']}/constraints/{failed['constraint_version_id']}/commitments/retry",
        headers={**session, **idem("retry-condition")},
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "ACTIVE"
    assert retried.json()["commitment_status"] == "CONFIRMED"
    after = client.get(
        f"/rooms/{room['decision_room_id']}/constraints/me", headers=session
    ).json()["constraints"][0]
    assert [item["status"] for item in after["commitment_attempts"]] == ["FAILED", "CONFIRMED"]


def test_failed_final_commitment_can_be_retried_for_all_empty_room(monkeypatch):
    monkeypatch.setattr(chain, "chain_enabled", lambda: True)
    attempts = itertools.count()

    def anchor(**_kwargs):
        if next(attempts) == 0:
            return {"status": "FAILED", "verification_mode": "ONCHAIN", "transactions": []}
        return {
            "status": "CONFIRMED", "verification_mode": "ONCHAIN",
            "decision_room_key": "0x" + "13" * 32,
            "onchain_decision_commitment": "0x" + "ab" * 32,
            "transactions": [],
        }

    monkeypatch.setattr(chain, "anchor_existing_decision", anchor)
    room = create_room()
    joined = [join(room, f"empty-{index}") for index in range(2)]
    for _, session in joined:
        confirm_input(room["decision_room_id"], session, "EMPTY")
    failed = client.post(
        f"/rooms/{room['decision_room_id']}/decision-runs",
        headers={**joined[0][1], **idem("failed-final")},
    )
    assert failed.json()["commitment_status"] == "COMMITMENT_FAILED"
    assert client.get(f"/rooms/{room['decision_room_id']}/final-decision").status_code == 409
    assert client.get(
        f"/rooms/{room['decision_room_id']}/receipts/me", headers=joined[0][1]
    ).status_code == 409

    retried = client.post(
        f"/rooms/{room['decision_room_id']}/final-decision/commitment/retry",
        headers={**joined[0][1], **idem("retry-final")},
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["commitment_status"] == "COMMITTED"
    assert retried.json()["decision_status"] == "COMPLETED"
    assert client.get(f"/rooms/{room['decision_room_id']}/final-decision").status_code == 200
