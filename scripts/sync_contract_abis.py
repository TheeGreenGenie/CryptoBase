import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = ROOT / "contracts" / "out"
ABI_TARGET = ROOT / "app" / "abis"
CONTRACTS = ["LendingPool", "MockERC20", "MockPriceOracle"]


def main():
    ABI_TARGET.mkdir(parents=True, exist_ok=True)
    copied = []

    for contract_name in CONTRACTS:
        artifact = ARTIFACT_ROOT / f"{contract_name}.sol" / f"{contract_name}.json"
        if not artifact.exists():
            raise FileNotFoundError(f"Missing Foundry artifact: {artifact}")

        data = json.loads(artifact.read_text(encoding="utf-8"))
        target = ABI_TARGET / f"{contract_name}.json"
        target.write_text(json.dumps(data["abi"], indent=2), encoding="utf-8")
        copied.append(str(target.relative_to(ROOT)))

    print("Copied ABIs:")
    for path in copied:
        print(f"- {path}")


if __name__ == "__main__":
    main()
