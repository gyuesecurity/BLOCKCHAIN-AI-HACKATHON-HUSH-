import json
from pathlib import Path

from hush.crypto import canonical_json, condition_commitment, input_leaf, input_root
from hush.fixtures import DEMO_CANDIDATES


ROOT = Path(__file__).resolve().parents[1]


def test_condition_commitment_vector():
    vector = json.loads((ROOT / "test-vectors/hash-v1.json").read_text(encoding="utf-8"))
    complete = {
        "protocol": "HUSH",
        "schema_version": "1",
        **vector["payload"],
        "salt": vector["salt"],
    }
    assert canonical_json(complete).decode("utf-8") == vector["canonical_json_utf8"]
    assert condition_commitment(vector["payload"], vector["salt"]) == vector["expected_keccak256"]


def test_published_dataset_matches_engine_fixture():
    published = json.loads((ROOT / "fixtures/demo-candidates-v1.json").read_text(encoding="utf-8"))
    assert published == DEMO_CANDIDATES


def test_constrained_empty_and_input_set_vectors():
    vector = json.loads((ROOT / "test-vectors/input-set-v1.json").read_text(encoding="utf-8"))
    empty = vector["empty"]
    complete = {
        "protocol": "HUSH", "schema_version": "1",
        **empty["payload"], "salt": empty["salt"],
    }
    assert canonical_json(complete).decode("utf-8") == empty["canonical_json_utf8"]
    assert condition_commitment(empty["payload"], empty["salt"]) == empty["expected_condition_commitment"]

    leaves = []
    for participant_input in vector["participant_inputs"]:
        expected = participant_input["expected_input_set_leaf"]
        payload = {key: value for key, value in participant_input.items() if key != "expected_input_set_leaf"}
        assert input_leaf(payload) == expected
        leaves.append(expected)
    assert input_root(list(reversed(leaves))) == vector["expected_input_set_root"]
