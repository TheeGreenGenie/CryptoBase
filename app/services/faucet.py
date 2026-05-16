from flask import current_app

from app.services.blockchain import checksum, get_contract, get_web3, to_raw_amount


def drip(user_address: str) -> str:
    """Mint collateral tokens to user_address. Returns the tx hash."""
    w3 = get_web3()
    private_key = current_app.config.get("FAUCET_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("FAUCET_PRIVATE_KEY is not configured")

    amount = current_app.config["FAUCET_AMOUNT"]
    raw_amount = to_raw_amount(amount)
    recipient = checksum(user_address)

    token = get_contract(current_app.config["COLLATERAL_TOKEN_ADDRESS"], "MockERC20")
    deployer = w3.eth.account.from_key(private_key)

    tx = token.functions.mint(recipient, raw_amount).build_transaction({
        "from": deployer.address,
        "chainId": current_app.config["CHAIN_ID"],
        "nonce": w3.eth.get_transaction_count(deployer.address),
        "gas": 100_000,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return tx_hash.hex()
