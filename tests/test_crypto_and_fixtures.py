import json
from pathlib import Path

from hush.crypto import canonical_json, condition_commitment
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

