#!/usr/bin/env python3
"""Deploy HushDecisionRegistry to the configured testnet (default Ethereum Sepolia).

Requires (env or .env):
  HUSH_CHAIN_RPC_URL       default https://ethereum-sepolia-rpc.publicnode.com
  HUSH_CHAIN_PRIVATE_KEY   funded deployer / relayer key (testnet only)
Optional:
  HUSH_CHAIN_RELAYER       relayer address to authorise (default: deployer)
  HUSH_CHAIN_ID            default 11155111
  HUSH_CHAIN_NETWORK_NAME  default "Ethereum Sepolia"

Prints the deployed address for HUSH_CHAIN_CONTRACT_ADDRESS and writes
contracts/deployments/<network>.json.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _envfile import load_dotenv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "contracts" / "build" / "HushDecisionRegistry.json"


def main() -> int:
    load_dotenv()
    try:
        from web3 import Web3
    except ModuleNotFoundError:
        print("web3가 필요합니다:  pip install -e '.[chain]'")
        return 1

    rpc_url = os.getenv("HUSH_CHAIN_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
    key = os.getenv("HUSH_CHAIN_PRIVATE_KEY")
    if not key:
        print("HUSH_CHAIN_PRIVATE_KEY 가 필요합니다 (scripts/new_wallet.py 로 생성).")
        return 1
    chain_id = int(os.getenv("HUSH_CHAIN_ID", "11155111"))
    network = os.getenv("HUSH_CHAIN_NETWORK_NAME", "Ethereum Sepolia")

    if not ARTIFACT.exists():
        print(f"빌드 산출물이 없습니다: {ARTIFACT}  ->  python scripts/compile_contract.py")
        return 1
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print(f"RPC 연결 실패: {rpc_url}")
        return 1

    account = w3.eth.account.from_key(key)
    relayer = os.getenv("HUSH_CHAIN_RELAYER", account.address)
    relayer = Web3.to_checksum_address(relayer)

    balance = w3.eth.get_balance(account.address)
    print(f"deployer : {account.address}")
    print(f"balance  : {w3.from_wei(balance, 'ether')} ETH  ({network}, chainId {chain_id})")
    print(f"relayer  : {relayer}")
    if balance == 0:
        print("잔액이 0입니다. faucet에서 먼저 충전하세요.")
        return 1

    contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", w3.eth.gas_price)
    try:
        priority = w3.eth.max_priority_fee
    except Exception:
        priority = w3.to_wei(1, "gwei")

    tx = contract.constructor(relayer).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": chain_id,
            "maxPriorityFeePerGas": priority,
            "maxFeePerGas": base_fee * 2 + priority,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"deploy tx: {tx_hash.hex()}  (waiting for receipt...)")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt["status"] != 1:
        print("배포 트랜잭션이 revert 되었습니다.")
        return 1

    address = receipt["contractAddress"]
    explorer = os.getenv("HUSH_CHAIN_EXPLORER", "https://sepolia.etherscan.io").rstrip("/")
    deployment = {
        "network": network,
        "chain_id": chain_id,
        "rpc_url": rpc_url,
        "contract_address": address,
        "relayer_address": relayer,
        "deployer_address": account.address,
        "deploy_tx_hash": tx_hash.hex() if tx_hash.hex().startswith("0x") else "0x" + tx_hash.hex(),
        "block_number": receipt["blockNumber"],
        "explorer_url": f"{explorer}/address/{address}",
        "compiler": artifact.get("compiler"),
    }
    slug = re.sub(r"[^a-z0-9]+", "-", network.lower()).strip("-")
    out = ROOT / "contracts" / "deployments" / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"deployed : {address}")
    print(f"explorer : {deployment['explorer_url']}")
    print(f"written  : {out.relative_to(ROOT)}")
    print()
    print(".env 에 추가:")
    print(f"HUSH_CHAIN_CONTRACT_ADDRESS={address}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
