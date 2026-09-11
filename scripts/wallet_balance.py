#!/usr/bin/env python3
"""Print an address' native balance across mainnet + common testnets.

Usage:
  python scripts/wallet_balance.py 0xYourAddress
  python scripts/wallet_balance.py            # uses HUSH_CHAIN_PRIVATE_KEY's address
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _envfile import load_dotenv  # noqa: E402

NETWORKS = [
    ("Ethereum Mainnet", "https://ethereum-rpc.publicnode.com"),
    ("Base Sepolia", "https://sepolia.base.org"),
    ("Ethereum Sepolia", "https://ethereum-sepolia-rpc.publicnode.com"),
]


def main() -> int:
    load_dotenv()
    try:
        from web3 import Web3
    except ModuleNotFoundError:
        print("web3가 필요합니다:  pip install -e '.[chain]'")
        return 1

    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        key = os.getenv("HUSH_CHAIN_PRIVATE_KEY")
        if not key:
            print("주소를 인자로 주거나 .env 에 HUSH_CHAIN_PRIVATE_KEY 를 설정하세요.")
            return 1
        from eth_account import Account

        address = Account.from_key(key).address

    address = Web3.to_checksum_address(address)
    print(f"address: {address}\n")
    for name, rpc in NETWORKS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
            balance = w3.from_wei(w3.eth.get_balance(address), "ether")
            print(f"  {name:<20} {balance} ETH")
        except Exception as exc:  # pragma: no cover - network dependent
            print(f"  {name:<20} 조회 실패 ({type(exc).__name__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
