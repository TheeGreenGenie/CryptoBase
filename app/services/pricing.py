from decimal import Decimal

from flask import current_app

STATIC_DEMO_PRICES = {
    "eth":   Decimal("2000"),
    "mweth": Decimal("2000"),
    "musdc": Decimal("1"),
}


def get_token_price_usd(token_address: str) -> Decimal:
    if current_app.config.get("FLASK_ENV") == "production":
        raise RuntimeError("Static demo prices are disabled in production")

    symbol = _symbol_for_address(token_address)
    if symbol in STATIC_DEMO_PRICES:
        return STATIC_DEMO_PRICES[symbol]
    raise ValueError(f"Unsupported asset: {token_address}")


def get_supported_assets() -> list[dict]:
    return [
        {"symbol": "ETH",   "address": "0x0000000000000000000000000000000000000000", "price_usd": "2000"},
        {"symbol": "mWETH", "address": current_app.config.get("COLLATERAL_TOKEN_ADDRESS", ""), "price_usd": "2000"},
        {"symbol": "mUSDC", "address": current_app.config.get("DEBT_TOKEN_ADDRESS", ""), "price_usd": "1"},
    ]


def _symbol_for_address(token_address: str) -> str:
    if token_address in ("0x0000000000000000000000000000000000000000", "eth"):
        return "eth"
    if token_address and token_address.lower() == (current_app.config.get("COLLATERAL_TOKEN_ADDRESS") or "").lower():
        return "mweth"
    if token_address and token_address.lower() == (current_app.config.get("DEBT_TOKEN_ADDRESS") or "").lower():
        return "musdc"
    return token_address.lower()
