import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from flask import current_app
from web3 import Web3

ABI_DIR = Path(__file__).resolve().parent.parent / "abis"
ERC20_MIN_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


@lru_cache(maxsize=1)
def get_web3() -> Web3:
    return Web3(Web3.HTTPProvider(current_app.config["RPC_URL"]))


def validate_chain() -> bool:
    web3 = get_web3()
    return web3.eth.chain_id == current_app.config["CHAIN_ID"]


def checksum(address: str) -> str:
    if not Web3.is_address(address):
        raise ValueError(f"Invalid address: {address}")
    return Web3.to_checksum_address(address)


@lru_cache(maxsize=16)
def load_abi(abi_name: str):
    if abi_name == "ERC20":
        return ERC20_MIN_ABI
    path = ABI_DIR / f"{abi_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing ABI file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_contract(address: str, abi_name: str):
    web3 = get_web3()
    return web3.eth.contract(address=checksum(address), abi=load_abi(abi_name))


def to_raw_amount(amount: str | Decimal, decimals: int = 18) -> int:
    value = Decimal(str(amount))
    if value <= 0:
        raise ValueError("Amount must be positive")
    return int(value * (Decimal(10) ** decimals))


def from_raw_amount(amount: int | str, decimals: int = 18) -> Decimal:
    return Decimal(str(amount)) / (Decimal(10) ** decimals)


def build_tx(from_address: str, contract_function, value: int = 0) -> dict:
    web3 = get_web3()
    sender = checksum(from_address)
    # Provide a default gas so build_transaction does not call eth_estimateGas
    # internally — that internal call surfaces contract reverts as unhandled
    # ContractCustomError exceptions before our own try/except below can run.
    tx = contract_function.build_transaction(
        {
            "from": sender,
            "chainId": current_app.config["CHAIN_ID"],
            "nonce": web3.eth.get_transaction_count(sender),
            "gas": 300_000,
            "value": value,
        }
    )
    try:
        tx["gas"] = web3.eth.estimate_gas(tx)
    except Exception:
        current_app.logger.warning("Gas estimation failed; using default 300 000")
    return _tx_for_metamask(tx)


def _tx_for_metamask(tx: dict) -> dict:
    """Convert integer fields to 0x hex strings so MetaMask accepts the payload."""
    int_fields = ("gas", "gasPrice", "maxFeePerGas", "maxPriorityFeePerGas", "nonce", "value", "chainId")
    out = dict(tx)
    for key in int_fields:
        if key in out and isinstance(out[key], int):
            out[key] = hex(out[key])
    return out


def get_native_balance(address: str) -> int:
    return get_web3().eth.get_balance(checksum(address))


def wait_for_receipt(tx_hash: str, timeout: int = 120) -> dict:
    return dict(get_web3().eth.wait_for_transaction_receipt(tx_hash, timeout=timeout))
