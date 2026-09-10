from copy import deepcopy
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["HUSH_DEMO_ADMIN_KEY"] = "local-demo-admin"

from hush.fixtures import DEMO_CANDIDATES
from hush.main import app
from hush.verification import verify_receipt_data


client = TestClient(app)
ADMIN = {"X-Demo-Admin-Key": "local-demo-admin"}
INPUTS = {
    "A": "15,000원 넘는 곳은 부담스러워요",
    "B": "가능하면 해산물은 피하고 싶어요",
    "C": "휠체어 경사로가 필요해요",
    "D": "21시 이전에 끝나야 해요",
}


def setup_function():
    assert client.post("/api/demo/admin/reset", headers=ADMIN).status_code == 200


def join_and_confirm_all():
    sessions = {}
    for participant, source_text in INPUTS.items():
        joined = client.post(
            f"/api/demo/participants/{participant}/join",
            json={"invite_code": f"HUSH-{participant}-2026"},
        )
        assert joined.status_code == 200
        headers = {"X-Participant-Session": joined.json()["participant_session"]}
        sessions[participant] = headers
        parsed = client.post(
            f"/api/demo/participants/{participant}/private-inputs/parse",
            headers=headers,
            json={"source_text": source_text},
        )
        assert parsed.status_code == 200
        assert parsed.json()["parser_mode"] == "DEMO_RULE_PARSER"
        confirmed = client.post(
            f"/api/demo/participants/{participant}/constraints/confirm",
            headers=headers,
            json={"draft_id": parsed.json()["draft_id"]},
        )
        assert confirmed.status_code == 200
    return sessions


def complete_demo():
    sessions = join_and_confirm_all()
    initial = client.post("/api/demo/participants/A/decision-runs", headers=sessions["A"])
    assert initial.json()["status"] == "INFEASIBLE"
    accepted = client.post("/api/demo/participants/A/proposal/accept", headers=sessions["A"])
    assert accepted.json()["decision"] == "ACCEPTED"
    final = client.post("/api/demo/participants/A/decision-runs", headers=sessions["A"])
    assert final.json()["status"] == "FEASIBLE"
    return sessions


def test_full_private_input_negotiation_and_verification_flow():
    sessions = join_and_confirm_all()
    initial = client.post("/api/demo/participants/A/decision-runs", headers=sessions["A"])
    assert initial.json()["status"] == "INFEASIBLE"

    shared = client.get("/api/demo/state").json()
    serialized = str(shared)
    assert "proposal" not in serialized
    assert "participant_pseudonym" not in serialized
    assert "15000" not in serialized

    assert client.get("/api/demo/participants/B", headers=sessions["B"]).json()["proposal"] is None
    proposal = client.get("/api/demo/participants/A", headers=sessions["A"]).json()["proposal"]
    assert proposal["proposed_constraint_value"]["amount"] == 17000

    accepted = client.post("/api/demo/participants/A/proposal/accept", headers=sessions["A"])
    assert accepted.json()["decision"] == "ACCEPTED"
    history = client.get("/api/demo/participants/A", headers=sessions["A"]).json()["constraint_version_history"]
    assert [(item["constraint_version"], item["status"]) for item in history] == [(1, "SUPERSEDED"), (2, "ACTIVE")]

    final = client.post("/api/demo/participants/A/decision-runs", headers=sessions["A"])
    assert final.json()["selected_candidate_id"] == "restaurant-04"
    verification = client.post("/api/demo/participants/A/verify", headers=sessions["A"]).json()
    assert verification["status"] == "VERIFIED"
    assert all(verification["checks"].values())
    public_receipt = client.get("/api/demo/participants/A/receipt", headers=sessions["A"]).json()
    assert "private_verification_material" not in public_receipt


def test_wrong_participant_session_cannot_read_or_accept_proposal():
    sessions = join_and_confirm_all()
    client.post("/api/demo/participants/A/decision-runs", headers=sessions["A"])
    assert client.get("/api/demo/participants/A", headers=sessions["B"]).status_code == 404
    assert client.post("/api/demo/participants/A/proposal/accept", headers=sessions["B"]).status_code == 404


def test_admin_endpoints_are_not_public():
    assert client.post("/api/demo/admin/reset").status_code == 404
    assert client.post("/api/demo/admin/seed-confirmed-inputs").status_code == 404


@pytest.mark.parametrize(
    "tamper",
    [
        lambda receipt: receipt["candidate"].update({"name": "공격자가 바꾼 결과"}),
        lambda receipt: receipt.update({"final_decision_hash": "0x" + "00" * 32}),
        lambda receipt: receipt.update({"decision_commitment": "0x" + "00" * 32}),
        lambda receipt: receipt["participant_inputs"][0].update({"condition_commitment": "0x" + "00" * 32}),
        lambda receipt: receipt["input_set_leaves"].pop(),
        lambda receipt: receipt["input_set_leaves"].append(receipt["input_set_leaves"][0]),
        lambda receipt: receipt.pop("candidate_dataset_hash"),
    ],
)
def test_tampered_receipt_is_invalid(tamper):
    sessions = complete_demo()
    receipt = deepcopy(client.get("/api/demo/participants/A/receipt/export", headers=sessions["A"]).json())
    tamper(receipt)
    engine = Path("backend/hush/engine.py").read_bytes()
    assert verify_receipt_data(receipt, DEMO_CANDIDATES, engine)["status"] == "INVALID"
