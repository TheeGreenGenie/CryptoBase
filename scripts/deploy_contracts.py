import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROADCAST = ROOT / "contracts" / "broadcast" / "Deploy.s.sol" / "31337" / "run-latest.json"

# Anvil account (0) — well-known test key, never use on mainnet
ANVIL_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def main():
    result = subprocess.run(
        [
            "forge",
            "script",
            "script/Deploy.s.sol",
            "--rpc-url",
            "http://127.0.0.1:8545",
            "--private-key",
            ANVIL_KEY,
            "--broadcast",
        ],
        cwd=ROOT / "contracts",
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(result.returncode)

    if not BROADCAST.exists():
        print("ERROR: broadcast file not found at", BROADCAST)
        raise SystemExit(1)

    data = json.loads(BROADCAST.read_text(encoding="utf-8"))
    transactions = data.get("transactions", [])

    # Map contract name → deployed address
    deployed = {
        tx["contractName"]: tx["contractAddress"]
        for tx in transactions
        if tx.get("transactionType") == "CREATE" and tx.get("contractName")
    }

    if not deployed:
        print("No CREATE transactions found in broadcast file.")
        raise SystemExit(1)

    # Print .env block ready to paste
    name_to_env = {
        "MockERC20": None,  # two instances — handled below
        "MockPriceOracle": "PRICE_ORACLE_ADDRESS",
        "LendingPool": "LENDING_POOL_ADDRESS",
    }

    # MockERC20 is deployed twice: collateral first, debt second
    erc20_addresses = [
        tx["contractAddress"]
        for tx in transactions
        if tx.get("transactionType") == "CREATE" and tx.get("contractName") == "MockERC20"
    ]

    print("\n" + "=" * 50)
    print("Deployed contracts — copy into .env")
    print("=" * 50)

    if len(erc20_addresses) >= 1:
        print(f"COLLATERAL_TOKEN_ADDRESS={erc20_addresses[0]}")
    if len(erc20_addresses) >= 2:
        print(f"DEBT_TOKEN_ADDRESS={erc20_addresses[1]}")

    for name, env_key in name_to_env.items():
        if env_key and name in deployed:
            print(f"{env_key}={deployed[name]}")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
