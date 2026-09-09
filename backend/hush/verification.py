from __future__ import annotations

from typing import Any

from .crypto import condition_commitment, hash_json, input_leaf, input_root, keccak256


def _verify_receipt_data(
    receipt: dict[str, Any], dataset: list[dict[str, Any]], engine_bytes: bytes
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["input_set_root_matches"] = input_root(receipt["input_set_leaves"]) == receipt["input_set_root"]
    checks["candidate_dataset_hash_matches"] = hash_json(dataset) == receipt["candidate_dataset_hash"]
    checks["engine_code_hash_matches"] = keccak256(engine_bytes) == receipt["engine_code_hash"]

    candidates = {item["candidate_id"]: item for item in dataset}
    candidate_id = receipt["candidate"].get("candidate_id")
    checks["candidate_matches_dataset"] = candidate_id in candidates and receipt["candidate"] == candidates[candidate_id]

    inputs = {item["constraint_version_id"]: item for item in receipt["participant_inputs"]}
    materials = {
        item["constraint_version_id"]: item
        for item in receipt["private_verification_material"]
    }
    checks["participant_has_input_evidence"] = bool(inputs) and inputs.keys() == materials.keys()
    commitment_ok = True
    leaf_ok = True
    inclusion_ok = True
    for version_id, entry in inputs.items():
        material = materials.get(version_id)
        if material is None:
            commitment_ok = leaf_ok = inclusion_ok = False
            continue
        expected_commitment = condition_commitment(material["condition_payload"], material["salt"])
        commitment_ok &= expected_commitment == entry["condition_commitment"]
        leaf_payload = {
            "decision_room_id": entry["decision_room_id"],
            "decision_run_id": entry["decision_run_id"],
            "participant_input_id": entry["participant_input_id"],
            "input_mode": entry["input_mode"],
            "constraint_version_id": entry["constraint_version_id"],
            "condition_commitment": entry["condition_commitment"],
        }
        expected_leaf = input_leaf(leaf_payload)
        leaf_ok &= expected_leaf == entry["input_set_leaf"]
        inclusion_ok &= entry["input_set_leaf"] in receipt["input_set_leaves"]
    checks["own_condition_commitment_matches"] = commitment_ok
    checks["own_input_leaf_matches"] = leaf_ok
    checks["own_input_included"] = inclusion_ok

    expected_final_hash = hash_json(
        {
            "protocol": "HUSH",
            "schema_version": "1",
            "final_decision_id": receipt["final_decision_id"],
            "candidate_id": candidate_id,
            "input_set_root": receipt["input_set_root"],
            "candidate_dataset_hash": receipt["candidate_dataset_hash"],
            "engine_version": receipt["engine_version"],
            "engine_code_hash": receipt["engine_code_hash"],
        }
    )
    checks["final_decision_hash_matches"] = expected_final_hash == receipt["final_decision_hash"]
    room_id = receipt["participant_inputs"][0]["decision_room_id"] if receipt["participant_inputs"] else ""
    expected_decision_commitment = hash_json(
        {
            "protocol": "HUSH",
            "schema_version": "1",
            "verification_mode": receipt["verification_mode"],
            "decision_room_id": room_id,
            "input_set_root": receipt["input_set_root"],
            "candidate_dataset_hash": receipt["candidate_dataset_hash"],
            "engine_version": receipt["engine_version"],
            "engine_code_hash": receipt["engine_code_hash"],
            "final_decision_hash": receipt["final_decision_hash"],
        }
    )
    checks["decision_commitment_matches"] = expected_decision_commitment == receipt["decision_commitment"]
    return {"status": "VERIFIED" if all(checks.values()) else "INVALID", "checks": checks}


def verify_receipt_data(
    receipt: dict[str, Any], dataset: list[dict[str, Any]], engine_bytes: bytes
) -> dict[str, Any]:
    try:
        return _verify_receipt_data(receipt, dataset, engine_bytes)
    except (IndexError, KeyError, TypeError, ValueError):
        return {"status": "INVALID", "checks": {"receipt_well_formed": False}}
