import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.models import AgentSuggestion, User
from app.models.agent import SuggestionCache
from app.services.crypto_prices import format_for_prompt, get_top_10
from app.services.risk import portfolio_summary

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """DeFi portfolio assistant (testnet). Given live crypto market data and portfolio state, suggest ONE action.
Actions: repay, supply, withdraw, borrow, swap, hold.
Return ONLY valid JSON — no markdown, no explanation:
{"action":"repay|supply|withdraw|borrow|swap|hold","title":"short title","rationale":"1-2 sentences citing market data","risk_level":"low|medium|high","params":{}}
Rules: never custody funds, never suggest liquidation, prefer hold/repay when uncertain."""

_VALID_ACTIONS = {"repay", "supply", "withdraw", "borrow", "swap", "hold"}
_VALID_RISK_LEVELS = {"low", "medium", "high"}
TARGET_SUGGESTIONS = 3
MAX_LLM_ATTEMPTS = 6

_PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_attr": "OPENAI_API_KEY",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-2-latest",
        "key_attr": "GROK_API_KEY",
    },
}


def _chat_completion(base_url: str, api_key: str, model: str, user_message: str) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.6,
        "max_tokens": 160,
    }
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json=payload, headers=headers, timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_llm_response(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
    if data.get("action") not in _VALID_ACTIONS:
        return None
    if data.get("risk_level") not in _VALID_RISK_LEVELS:
        return None
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        return None
    if not isinstance(data.get("rationale"), str) or not data["rationale"].strip():
        return None
    return data


def _build_user_message(user: User, summary: dict, extra_context: str = "") -> str:
    market_table = format_for_prompt(get_top_10())
    base = (
        f"{market_table}\n\n"
        f"Risk tolerance:{user.risk_tolerance} Collateral:${summary['collateral_usd']} "
        f"Debt:${summary['debt_usd']} HF:{summary['health_factor']} Risk:{summary['risk_class']}"
    )
    if extra_context:
        base += f"\n{extra_context}"
    return base


def _probe(url: str, timeout: float = 2.0) -> bool:
    """Return True if the host is reachable — used to skip slow timeouts."""
    try:
        httpx.get(url, timeout=timeout)
        return True
    except Exception:
        return False


def _try_provider(name: str, user_message: str) -> str | None:
    from flask import current_app
    cfg = _PROVIDERS[name]
    api_key = current_app.config.get(cfg["key_attr"], "")
    if not api_key:
        return None
    try:
        return _chat_completion(cfg["base_url"], api_key, cfg["model"], user_message)
    except Exception as exc:
        log.warning("LLM provider %s failed: %s", name, exc)
        return None


def _try_qwen_local(user_message: str) -> str | None:
    from flask import current_app
    base_url = current_app.config.get("QWEN_BASE_URL", "http://localhost:11434/v1")
    model = current_app.config.get("QWEN_MODEL", "qwen2.5:7b")
    # Quick probe — avoids waiting 60 s when Ollama isn't running
    if not _probe(base_url.rstrip("/").rsplit("/", 1)[0]):
        log.debug("Ollama unreachable, skipping local LLM")
        return None
    try:
        return _chat_completion(base_url, "", model, user_message)
    except Exception as exc:
        log.warning("Local Qwen fallback failed: %s", exc)
        return None


def _call_llm(user_message: str) -> str | None:
    from flask import current_app
    provider = current_app.config.get("LLM_PROVIDER", "none").lower()
    raw = None
    if provider in _PROVIDERS:
        raw = _try_provider(provider, user_message)
    if raw is None:
        raw = _try_qwen_local(user_message)
    return raw


def _llm_is_available() -> bool:
    """Fast check: returns True if at least one LLM backend is reachable."""
    from flask import current_app
    provider = current_app.config.get("LLM_PROVIDER", "none").lower()
    if provider in _PROVIDERS:
        key = current_app.config.get(_PROVIDERS[provider]["key_attr"], "")
        if key:
            return True  # assume cloud provider is up if key is set
    base_url = current_app.config.get("QWEN_BASE_URL", "http://localhost:11434/v1")
    return _probe(base_url.rstrip("/").rsplit("/", 1)[0])


def _save_to_cache(data: dict) -> SuggestionCache:
    """Insert a new cache entry or return the existing one with the same hash."""
    from app.extensions import db
    content_hash = SuggestionCache.make_hash(data["action"], data["title"], data["rationale"])
    existing = SuggestionCache.query.filter_by(content_hash=content_hash).one_or_none()
    if existing:
        return existing
    entry = SuggestionCache(
        content_hash=content_hash,
        suggestion_type=data["action"],
        title=data["title"],
        rationale=data["rationale"],
        recommended_action={"action": data["action"], "params": data.get("params", {})},
        risk_level=data["risk_level"],
        source="llm",
        is_shareable=SuggestionCache.is_safe_to_share(data["action"], data["risk_level"]),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.session.add(entry)
    db.session.flush()  # populate entry.id without committing
    return entry


def _suggestion_from_cache(user: User, entry: SuggestionCache) -> AgentSuggestion:
    return AgentSuggestion(
        user_id=user.id,
        cache_id=entry.id,
        suggestion_type=entry.suggestion_type,
        title=entry.title,
        rationale=entry.rationale,
        recommended_action=entry.recommended_action,
        risk_level=entry.risk_level,
        source=entry.source,
        expires_at=entry.expires_at,
    )


def _already_seen_cache_ids(user_id: int) -> set[int]:
    """Cache IDs the user already has an AgentSuggestion for."""
    rows = (
        AgentSuggestion.query
        .filter(AgentSuggestion.user_id == user_id, AgentSuggestion.cache_id.isnot(None))
        .with_entities(AgentSuggestion.cache_id)
        .all()
    )
    return {r[0] for r in rows}


def _rejected_cache_ids(user_id: int) -> set[int]:
    """Cache IDs the user explicitly rejected — never re-surface these."""
    rows = (
        AgentSuggestion.query
        .filter(
            AgentSuggestion.user_id == user_id,
            AgentSuggestion.cache_id.isnot(None),
            AgentSuggestion.status == "rejected",
        )
        .with_entities(AgentSuggestion.cache_id)
        .all()
    )
    return {r[0] for r in rows}


def generate_rule_suggestions(user: User) -> list[AgentSuggestion]:
    summary = portfolio_summary(user.id)
    risk_class = summary["risk_class"]
    suggestions = []

    if risk_class in {"danger", "liquidatable"}:
        suggestions.append(AgentSuggestion(
            user_id=user.id,
            suggestion_type="repay",
            title="Reduce liquidation risk",
            rationale="Your health factor is low. Repaying debt or adding collateral is the safest next action.",
            recommended_action={"action": "repay", "amount": "review_current_debt"},
            risk_level="high",
            source="rules",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ))
    elif risk_class == "watch":
        suggestions.append(AgentSuggestion(
            user_id=user.id,
            suggestion_type="risk_alert",
            title="Watch collateral buffer",
            rationale="Your position is still above liquidation range, but the collateral buffer is narrowing.",
            recommended_action={"action": "hold_or_repay"},
            risk_level="medium",
            source="rules",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))

    if not suggestions and user.risk_tolerance == "aggressive":
        suggestions.append(AgentSuggestion(
            user_id=user.id,
            suggestion_type="supply",
            title="Review idle collateral",
            rationale="Aggressive settings allow higher exposure, but this MVP requires manual review before supplying more collateral.",
            recommended_action={"action": "supply", "amount": "manual"},
            risk_level="low",
            source="rules",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))

    return suggestions


def generate_and_cache_suggestions(user: User) -> tuple[list[AgentSuggestion], bool]:
    """
    Build a set of suggestions for this user up to TARGET_SUGGESTIONS (3).

    Strategy:
      1. Check shared cache for shareable suggestions the user hasn't seen yet.
      2. Call LLM (with retry loop) until total reaches TARGET_SUGGESTIONS or
         MAX_LLM_ATTEMPTS is exhausted, deduplicating by content hash each time.

    Returns (new_suggestions, llm_was_called).
    """
    from app.extensions import db

    now = datetime.now(timezone.utc)
    summary = portfolio_summary(user.id)
    seen_ids = _already_seen_cache_ids(user.id)
    rejected_ids = _rejected_cache_ids(user.id)
    new_suggestions: list[AgentSuggestion] = []

    # 1. Pull shareable cached entries the user hasn't seen and hasn't rejected
    cached = (
        SuggestionCache.query
        .filter(
            SuggestionCache.is_shareable == True,  # noqa: E712
            SuggestionCache.expires_at > now,
        )
        .order_by(SuggestionCache.created_at.desc())
        .all()
    )
    for entry in cached:
        if len(new_suggestions) >= TARGET_SUGGESTIONS:
            break
        if entry.id not in seen_ids and entry.id not in rejected_ids:
            new_suggestions.append(_suggestion_from_cache(user, entry))
            seen_ids.add(entry.id)

    if len(new_suggestions) >= TARGET_SUGGESTIONS:
        for s in new_suggestions:
            db.session.add(s)
        db.session.commit()
        return new_suggestions, False

    # 2. Call LLM until we reach TARGET_SUGGESTIONS, avoiding duplicates
    llm_called = False
    if not _llm_is_available():
        log.info("No LLM backend reachable; skipping LLM suggestions")
    else:
        llm_called = True
        existing_hashes: set[str] = {
            e.content_hash for e in SuggestionCache.query.with_entities(SuggestionCache.content_hash).all()
        }
        consecutive_failures = 0
        attempts = 0

        while len(new_suggestions) < TARGET_SUGGESTIONS and attempts < MAX_LLM_ATTEMPTS:
            attempts += 1
            seen_titles = [s.title for s in new_suggestions]
            extra = f"Already suggested this session: {seen_titles}. Give a different suggestion." if seen_titles else ""
            raw = _call_llm(_build_user_message(user, summary, extra))
            if raw is None:
                consecutive_failures += 1
                log.warning("LLM returned nothing on attempt %d", attempts)
                if consecutive_failures >= 2:
                    log.warning("Two consecutive LLM failures; aborting loop")
                    break
                continue

            consecutive_failures = 0
            data = _parse_llm_response(raw)
            if data is None:
                log.warning("Unparseable LLM response attempt %d: %r", attempts, raw[:200])
                continue

            content_hash = SuggestionCache.make_hash(data["action"], data["title"], data["rationale"])
            if content_hash in existing_hashes:
                log.debug("Duplicate LLM response skipped (attempt %d)", attempts)
                continue

            existing_hashes.add(content_hash)
            entry = _save_to_cache(data)
            new_suggestions.append(_suggestion_from_cache(user, entry))
            seen_ids.add(entry.id)

    for s in new_suggestions:
        db.session.add(s)
    db.session.commit()
    return new_suggestions, llm_called
