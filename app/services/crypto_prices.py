import logging
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_cache: Optional[dict] = None
_cache_ts: float = 0.0

_COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
    "&sparkline=false&price_change_percentage=24h"
)


def get_top_10() -> list[dict]:
    """Return top-10 cryptos by market cap from CoinGecko, cached for 5 minutes."""
    global _cache, _cache_ts
    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        return _cache

    try:
        resp = httpx.get(_COINGECKO_URL, timeout=10.0, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        _cache = [
            {
                "rank": i + 1,
                "symbol": coin["symbol"].upper(),
                "name": coin["name"],
                "price_usd": coin["current_price"],
                "change_24h_pct": round(coin.get("price_change_percentage_24h") or 0.0, 2),
                "market_cap_usd": coin["market_cap"],
            }
            for i, coin in enumerate(data)
        ]
        _cache_ts = time.time()
        log.debug("CoinGecko top-10 refreshed")
        return _cache
    except Exception as exc:
        log.warning("CoinGecko fetch failed: %s", exc)
        return _cache or []


def format_for_prompt(coins: list[dict]) -> str:
    """Format coin list as a compact table for inclusion in LLM prompts."""
    if not coins:
        return "Market data unavailable."
    lines = ["Top 10 cryptocurrencies by market cap (live):"]
    lines.append(f"{'#':<3} {'Symbol':<8} {'Price (USD)':>14} {'24h %':>8}")
    lines.append("-" * 37)
    for c in coins:
        change = f"{c['change_24h_pct']:+.2f}%"
        lines.append(f"{c['rank']:<3} {c['symbol']:<8} ${c['price_usd']:>13,.2f} {change:>8}")
    return "\n".join(lines)
