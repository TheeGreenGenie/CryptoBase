from decimal import Decimal

from flask import current_app

from app.services.blockchain import build_tx, get_contract, to_raw_amount
from app.services.pricing import get_supported_assets

DEFAULT_SLIPPAGE_BPS = 50
MIN_SLIPPAGE_BPS = 10
MAX_SLIPPAGE_BPS = 500


def quote_swap(token_in: str, token_out: str, amount: str, slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> dict:
    _validate_slippage(slippage_bps)
    assets = {asset["symbol"]: Decimal(asset["price_usd"]) for asset in get_supported_assets()}
    if token_in not in assets or token_out not in assets or token_in == token_out:
        raise ValueError("Unsupported token pair")

    amount_decimal = Decimal(str(amount))
    if amount_decimal <= 0:
        raise ValueError("Amount must be positive")

    gross_out = (amount_decimal * assets[token_in]) / assets[token_out]
    min_out = gross_out * (Decimal(10_000 - slippage_bps) / Decimal(10_000))
    return {
        "token_in": token_in,
        "token_out": token_out,
        "amount_in": str(amount_decimal),
        "quoted_amount_out": str(gross_out),
        "min_amount_out": str(min_out),
        "slippage_bps": slippage_bps,
        "mode": "demo_quote",
    }


def build_swap_tx(
    user_address: str, token_in: str, token_out: str, amount: str, slippage_bps: int = DEFAULT_SLIPPAGE_BPS
) -> dict:
    router_address = current_app.config.get("UNISWAP_ROUTER_ADDRESS")
    if not router_address:
        raise RuntimeError("Swap router is not configured; quote-only demo mode is active")

    quote_swap(token_in, token_out, amount, slippage_bps)
    router = get_contract(router_address, "UniswapRouter")
    raw_amount = to_raw_amount(amount)
    return build_tx(user_address, router.functions.exactInputSingle(token_in, token_out, raw_amount))


def _validate_slippage(slippage_bps: int):
    if slippage_bps < MIN_SLIPPAGE_BPS or slippage_bps > MAX_SLIPPAGE_BPS:
        raise ValueError("Slippage must be between 10 and 500 basis points")
