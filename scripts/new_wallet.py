#!/usr/bin/env python3
"""Generate a throwaway relayer wallet for the demo.

TESTNET ONLY. Never send mainnet funds to this address and never commit the key.
Fund the printed address from a Sepolia faucet, then put the private key in
`.env` as HUSH_CHAIN_PRIVATE_KEY.
"""

from __future__ import annotations

import secrets


def _hex(value: bytes | str) -> str:
    text = value.hex() if isinstance(value, (bytes, bytearray)) else str(value)
    return text if text.startswith("0x") else "0x" + text


def main() -> int:
    try:
        from eth_account import Account
    except ModuleNotFoundError:
        print("web3가 필요합니다:  pip install -e '.[chain]'")
        return 1

    account = Account.from_key(secrets.token_bytes(32))
    private_key = _hex(bytes(account.key))

    print("=== HUSH demo relayer wallet (TESTNET ONLY) ===")
    print(f"address      : {account.address}")
    print(f"private key  : {private_key}")
    print()
    print("다음 단계:")
    print(f"  1. 이 주소를 Sepolia faucet에서 충전  ->  {account.address}")
    print("     - https://sepolia-faucet.pk910.de  (로그인 불필요, 브라우저 PoW)")
    print("     - https://cloud.google.com/application/web3/faucet/ethereum/sepolia")
    print("  2. .env 에 아래 줄 추가 (커밋 금지):")
    print(f"     HUSH_CHAIN_PRIVATE_KEY={private_key}")
    print("     HUSH_CHAIN_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com")
    print("  3. python scripts/deploy_contract.py  로 레지스트리 배포")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
