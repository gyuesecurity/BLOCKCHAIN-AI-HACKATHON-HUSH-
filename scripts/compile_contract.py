#!/usr/bin/env python3
"""Compile contracts/HushDecisionRegistry.sol into the committed build artifact.

Uses the same solc the check suite uses (`npx solc@0.8.24`), so it needs Node.
Output: contracts/build/HushDecisionRegistry.json  { abi, bytecode }.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "HushDecisionRegistry.sol"
OUT = ROOT / "contracts" / "build" / "HushDecisionRegistry.json"
SOLC_VERSION = "0.8.24"


def main() -> int:
    if not SOURCE.exists():
        print(f"소스를 찾을 수 없습니다: {SOURCE}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            "npx",
            "--yes",
            f"solc@{SOLC_VERSION}",
            "--optimize",
            "--optimize-runs",
            "200",
            "--bin",
            "--abi",
            "-o",
            tmp,
            str(SOURCE),
        ]
        try:
            subprocess.run(cmd, check=True, cwd=ROOT, shell=(sys.platform == "win32"))
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"solc 컴파일 실패: {exc}")
            return 1

        tmp_path = Path(tmp)
        abi_file = next(tmp_path.glob("*HushDecisionRegistry.abi"))
        bin_file = next(tmp_path.glob("*HushDecisionRegistry.bin"))
        artifact = {
            "contractName": "HushDecisionRegistry",
            "compiler": f"solcjs {SOLC_VERSION}, optimizer runs=200",
            "abi": json.loads(abi_file.read_text(encoding="utf-8")),
            "bytecode": "0x" + bin_file.read_text(encoding="utf-8").strip(),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  (abi entries: {len(artifact['abi'])}, "
          f"bytecode bytes: {(len(artifact['bytecode']) - 2) // 2})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
