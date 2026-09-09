#!/usr/bin/env bash
set -euo pipefail

python_bin=${PYTHON_BIN:-python3}

"$python_bin" -m pytest -q
node --check frontend/app.js
node --check frontend/participant.js
"$python_bin" -m compileall -q backend scripts tests

contract_output=$(mktemp -d /tmp/hush-solc-XXXXXX)
npx --yes solc@0.8.24 --bin --abi contracts/HushDecisionRegistry.sol -o "$contract_output"

git diff --check
echo "HUSH checks passed"
