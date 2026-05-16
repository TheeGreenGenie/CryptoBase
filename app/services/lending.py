from flask import current_app

from app.services.blockchain import build_tx, checksum, get_contract, get_web3, to_raw_amount

ETH_ADDRESS = "0x0000000000000000000000000000000000000000"


def lending_pool():
    return get_contract(_required_config("LENDING_POOL_ADDRESS"), "LendingPool")


def debt_token():
    return get_contract(_required_config("DEBT_TOKEN_ADDRESS"), "ERC20")


def build_supply_tx(user_address: str, amount: str, token_address: str = ETH_ADDRESS) -> dict:
    user_address = checksum(user_address)
    raw_amount = to_raw_amount(amount)
    pool = lending_pool()
    token_address = checksum(token_address)

    if token_address == checksum(ETH_ADDRESS):
        # Native ETH — send as tx value, no approval needed
        tx = build_tx(user_address, pool.functions.supply(token_address, 0), value=raw_amount)
        return {"tx": tx, "needs_approval": False}
    else:
        # ERC20 — check allowance first
        token = get_contract(token_address, "ERC20")
        pool_address = checksum(_required_config("LENDING_POOL_ADDRESS"))
        allowance = token.functions.allowance(user_address, pool_address).call()
        if allowance < raw_amount:
            return {
                "tx": build_tx(user_address, token.functions.approve(pool_address, raw_amount)),
                "needs_approval": True,
            }
        return {
            "tx": build_tx(user_address, pool.functions.supply(token_address, raw_amount)),
            "needs_approval": False,
        }


def build_withdraw_tx(user_address: str, amount: str, token_address: str = ETH_ADDRESS) -> dict:
    user_address = checksum(user_address)
    raw_amount = to_raw_amount(amount)
    pool = lending_pool()
    token_address = checksum(token_address)

    collateral_balance = pool.functions.collateralBalance(user_address, token_address).call()
    symbol = _token_symbol(token_address)
    if raw_amount > collateral_balance:
        raise ValueError(
            f"Cannot withdraw {_fmt(raw_amount)} {symbol} — balance is {_fmt(collateral_balance)} {symbol}."
        )

    # Pre-check: ensure remaining collateral still covers debt at 150% min ratio
    debt_usd = pool.functions.debtValueUsd(user_address).call()
    if debt_usd > 0:
        collateral_usd = pool.functions.collateralValueUsd(user_address).call()
        oracle_addr = pool.functions.oracle().call()
        oracle = get_contract(oracle_addr, "MockPriceOracle")
        token_price = oracle.functions.getPrice(token_address).call()
        withdraw_usd = raw_amount * token_price // int(1e18)
        remaining_usd = collateral_usd - withdraw_usd
        min_required_usd = debt_usd * 15000 // 10000
        if remaining_usd < min_required_usd:
            max_withdraw_usd = collateral_usd - min_required_usd
            max_withdraw = max_withdraw_usd * int(1e18) // token_price if token_price else 0
            raise ValueError(
                f"Cannot withdraw {_fmt(raw_amount)} {symbol} — would undercollateralize position. "
                f"Maximum safe withdrawal is ~{_fmt(max(max_withdraw, 0))} {symbol}."
            )

    return {"tx": build_tx(user_address, pool.functions.withdraw(token_address, raw_amount)), "needs_approval": False}


def build_borrow_tx(user_address: str, amount: str) -> dict:
    user_address = checksum(user_address)
    raw_amount = to_raw_amount(amount)
    pool = lending_pool()
    collateral_usd = pool.functions.collateralValueUsd(user_address).call()
    debt_usd = pool.functions.debtValueUsd(user_address).call()
    max_debt_usd = collateral_usd * 10000 // 15000
    if debt_usd >= max_debt_usd:
        raise ValueError("Cannot borrow — collateral ratio would be exceeded. Supply more collateral first.")
    debt_token_addr = pool.functions.debtToken().call()
    oracle_addr = pool.functions.oracle().call()
    oracle = get_contract(oracle_addr, "MockPriceOracle")
    debt_price = oracle.functions.getPrice(debt_token_addr).call()
    borrow_usd = raw_amount * debt_price // int(1e18)
    if debt_usd + borrow_usd > max_debt_usd:
        max_borrow_usd = max_debt_usd - debt_usd
        max_tokens = max_borrow_usd * int(1e18) // debt_price if debt_price else 0
        raise ValueError(
            f"Borrow amount too large — maximum borrowable is ~{_fmt(max_tokens)} mUSDC given current collateral."
        )
    return {"tx": build_tx(user_address, pool.functions.borrow(raw_amount)), "needs_approval": False}


def build_repay_tx(user_address: str, amount: str) -> dict:
    user_address = checksum(user_address)
    raw_amount = to_raw_amount(amount)
    pool = lending_pool()
    debt_balance = pool.functions.debtBalance(user_address).call()
    if raw_amount > debt_balance:
        raise ValueError(
            f"Cannot repay {_fmt(raw_amount)} mUSDC — debt balance is only {_fmt(debt_balance)} mUSDC."
        )
    token = debt_token()
    pool_address = checksum(_required_config("LENDING_POOL_ADDRESS"))
    allowance = token.functions.allowance(user_address, pool_address).call()
    if allowance < raw_amount:
        return {"tx": build_tx(user_address, token.functions.approve(pool_address, raw_amount)), "needs_approval": True}
    return {"tx": build_tx(user_address, pool.functions.repay(raw_amount)), "needs_approval": False}


def read_position(user_address: str) -> dict:
    user_address = checksum(user_address)
    pool = lending_pool()
    collateral_positions = []
    for t in _collateral_tokens():
        addr = checksum(t["address"])
        raw = pool.functions.collateralBalance(user_address, addr).call()
        if raw > 0:
            collateral_positions.append({
                "symbol": t["symbol"],
                "address": t["address"],
                "amount": f"{raw / 1e18:.6f}",
                "amount_raw": str(raw),
            })

    debt_raw = pool.functions.debtBalance(user_address).call()
    health_factor_raw = pool.functions.healthFactor(user_address).call()
    collateral_usd = pool.functions.collateralValueUsd(user_address).call()
    debt_usd = pool.functions.debtValueUsd(user_address).call()

    return {
        "collateral_positions": collateral_positions,
        "debt_raw": str(debt_raw),
        "health_factor_raw": str(health_factor_raw),
        "debt_tokens": f"{debt_raw / 1e18:.4f}" if debt_raw > 0 else None,
        "collateral_usd": f"{collateral_usd / 1e18:.2f}",
        "debt_usd": f"{debt_usd / 1e18:.2f}",
        "debt_symbol": "mUSDC",
    }


def _collateral_tokens() -> list:
    tokens = [{"address": ETH_ADDRESS, "symbol": "ETH", "name": "Ethereum"}]
    wbtc = current_app.config.get("WBTC_TOKEN_ADDRESS")
    if wbtc:
        tokens.append({"address": wbtc, "symbol": "mWBTC", "name": "Mock Wrapped Bitcoin"})
    return tokens


def _token_symbol(address: str) -> str:
    addr_lower = address.lower()
    for t in _collateral_tokens():
        if t["address"].lower() == addr_lower:
            return t["symbol"]
    return "tokens"


def _fmt(raw: int, decimals: int = 18) -> str:
    return f"{raw / 10**decimals:.6f}"


def _required_config(name: str) -> str:
    value = current_app.config.get(name)
    if not value:
        raise RuntimeError(f"Missing required config: {name}")
    return value
