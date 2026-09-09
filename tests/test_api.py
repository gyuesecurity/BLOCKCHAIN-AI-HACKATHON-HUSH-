from fastapi.testclient import TestClient

from hush.main import app


client = TestClient(app)
A_SESSION = {"X-Participant-Session": "demo-session-a"}
B_SESSION = {"X-Participant-Session": "demo-session-b"}


def setup_function():
    client.post("/api/demo/reset")


def test_full_demo_flow_and_local_verification():
    seeded = client.post("/api/demo/seed-confirmed-inputs")
    assert seeded.status_code == 200
    assert seeded.json()["status"] == "READY"

    initial = client.post("/api/demo/decision-runs")
    assert initial.json()["status"] == "INFEASIBLE"

    shared = client.get("/api/demo/state").json()
    assert "proposal" not in shared
    assert "participant_pseudonym" not in shared

    assert client.get("/api/demo/participants/B", headers=B_SESSION).json()["proposal"] is None
    proposal = client.get("/api/demo/participants/A", headers=A_SESSION).json()["proposal"]
    assert proposal["proposed_constraint_value"]["amount"] == 17000

    accepted = client.post("/api/demo/participants/A/proposal/accept", headers=A_SESSION)
    assert accepted.json()["decision"] == "ACCEPTED"
    final = client.post("/api/demo/decision-runs")
    assert final.json()["status"] == "FEASIBLE"
    assert final.json()["selected_candidate_id"] == "restaurant-01"

    verification = client.post("/api/demo/participants/A/verify", headers=A_SESSION).json()
    assert verification["status"] == "VERIFIED"
    assert verification["verification_mode"] == "LOCAL"


def test_non_owner_cannot_read_or_accept_private_proposal():
    client.post("/api/demo/seed-confirmed-inputs")
    client.post("/api/demo/decision-runs")
    assert client.get("/api/demo/participants/A", headers=B_SESSION).status_code == 404
    response = client.post("/api/demo/participants/A/proposal/accept", headers=B_SESSION)
    assert response.status_code == 404
