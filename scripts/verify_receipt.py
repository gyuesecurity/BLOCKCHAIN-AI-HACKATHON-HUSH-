#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from hush.verification import verify_receipt_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a HUSH local demo receipt")
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    dataset = json.loads(
        (REPOSITORY_ROOT / receipt["candidate_dataset_uri"]).read_text(encoding="utf-8")
    )
    engine = (REPOSITORY_ROOT / receipt["engine_artifact_uri"]).read_bytes()
    result = verify_receipt_data(receipt, dataset, engine)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
