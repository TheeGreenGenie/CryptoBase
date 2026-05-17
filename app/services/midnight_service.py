"""
Midnight Privacy Service

Generates cryptographic commitments of user position data and produces
zero-knowledge attestations via the Midnight network (or local demo mode
when no Midnight node is configured).

The service NEVER returns raw collateral or debt amounts — only commitment
hashes and the derived public attestation (is_overcollateralized, risk_class).
"""

import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation

import requests
from flask import current_app

from app.services import risk as risk_service

logger = logging.getLogger(__name__)

_RISK_CLASS_LABELS = {
    "healthy":      {"label": "Healthy",      "code": 0},
    "watch":        {"label": "Watch",        "code": 1},
    "danger":       {"label": "Danger",       "code": 2},
    "liquidatable": {"label": "Liquidatable", "code": 3},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attest_position(wallet_address: str, user_id: int | None = None) -> dict:
    """
    Derive a ZK-style attestation for a wallet's current lending position.

    Returns a dict with commitment hashes and public attestation only.
    Actual collateral / debt amounts are never included in the return value.

    Args:
        wallet_address: EVM wallet address (checksummed or lowercase).
        user_id: DB user id — used to pull DB positions when chain is unreachable.

    Returns:
        {
            collateral_commit: str   # hex SHA-256 commitment of collateral USD
            debt_commit:       str   # hex SHA-256 commitment of debt USD
            proof_hash:        str   # hex SHA-256(collateral_commit || debt_commit)
            is_overcollateralized: bool
            risk_class:        str   # healthy | watch | danger | liquidatable
            risk_label:        str   # human-readable label
            mode:              str   # "midnight" | "local_demo"
        }
    """
    collateral_usd, debt_usd, risk_class = _read_position_amounts(wallet_address, user_id)

    salt = _derive_salt(wallet_address)
    collateral_cents = int(Decimal(str(collateral_usd)) * 100)
    debt_cents       = int(Decimal(str(debt_usd)) * 100)

    collateral_commit = commit_value(collateral_cents, salt)
    debt_commit       = commit_value(debt_cents, salt)
    proof_hash        = _derive_proof_hash(collateral_commit, debt_commit)

    is_overcollat = (
        debt_cents == 0 or (collateral_cents * 10_000) >= (debt_cents * 15_000)
    )

    payload = {
        "wallet":              wallet_address.lower(),
        "collateral_commit":   collateral_commit,
        "debt_commit":         debt_commit,
        "proof_hash":          proof_hash,
        "is_overcollateralized": is_overcollat,
        "risk_class":          risk_class,
        "risk_label":          _RISK_CLASS_LABELS.get(risk_class, {}).get("label", risk_class.title()),
    }

    # Try to push attestation to the Midnight node.
    rpc_url = current_app.config.get("MIDNIGHT_RPC_URL", "")
    mode = "local_demo"
    if rpc_url:
        try:
            _call_midnight_rpc(
                rpc_url,
                "attest_health",
                {
                    "user":              wallet_address.lower(),
                    "collateral_commit": collateral_commit,
                    "debt_commit":       debt_commit,
                    "proof_hash":        proof_hash,
                },
            )
            mode = "midnight"
        except Exception as exc:
            logger.warning("Midnight RPC call failed, falling back to local demo: %s", exc)

    payload["mode"] = mode
    return payload


def get_public_attestation(wallet_address: str, user_id: int | None = None) -> dict:
    """
    Return only the public-facing fields of an attestation (no amounts).
    Safe to expose to anyone — equivalent to querying the Midnight public ledger.
    """
    result = attest_position(wallet_address, user_id)
    return {
        "proof_hash":            result["proof_hash"],
        "is_overcollateralized": result["is_overcollateralized"],
        "risk_class":            result["risk_class"],
        "risk_label":            result["risk_label"],
        "mode":                  result["mode"],
    }


def commit_value(amount_cents: int, salt: bytes) -> str:
    """
    Produce a SHA-256 commitment: SHA-256(amount_bytes || salt).
    The amount is never recoverable from the commitment without the salt.
    """
    amount_bytes = amount_cents.to_bytes(8, byteorder="big")
    digest = hashlib.sha256(amount_bytes + salt).hexdigest()
    return digest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_position_amounts(wallet_address: str, user_id: int | None) -> tuple:
    """
    Returns (collateral_usd, debt_usd, risk_class) as strings/Decimals.

    Tries live chain data first; falls back to DB positions; returns zeros
    if neither is available (new user with no position).
    """
    # Attempt 1: live chain read via lending service
    try:
        from app.services import lending as lending_service
        pos = lending_service.read_position(wallet_address)
        collateral_usd = Decimal(pos["collateral_usd"])
        debt_usd       = Decimal(pos["debt_usd"])
        hf             = risk_service.calculate_health_factor(collateral_usd, debt_usd)
        risk_class     = risk_service.classify_health_factor(hf)
        return collateral_usd, debt_usd, risk_class
    except Exception:
        pass  # chain not configured or unreachable — try DB next

    # Attempt 2: DB positions via risk service
    if user_id is not None:
        try:
            summary    = risk_service.portfolio_summary(user_id)
            return (
                Decimal(summary["collateral_usd"]),
                Decimal(summary["debt_usd"]),
                summary["risk_class"],
            )
        except Exception:
            pass

    # No position data available — healthy/zero state
    return Decimal("0"), Decimal("0"), "healthy"


def _derive_salt(wallet_address: str) -> bytes:
    """
    Derive a deterministic per-wallet salt from the app's SECRET_KEY.
    The salt is consistent across calls for the same wallet so commitments
    are reproducible, while remaining opaque to anyone without the secret key.
    """
    secret = current_app.config.get("SECRET_KEY", "dev-only-change-me").encode()
    return hmac.new(secret, wallet_address.lower().encode(), hashlib.sha256).digest()


def _derive_proof_hash(collateral_commit: str, debt_commit: str) -> str:
    """
    Derive the public proof hash: SHA-256(collateral_commit_bytes || debt_commit_bytes).
    This is the fingerprint recorded in the Midnight public ledger.
    """
    combined = bytes.fromhex(collateral_commit) + bytes.fromhex(debt_commit)
    return hashlib.sha256(combined).hexdigest()


def _call_midnight_rpc(base_url: str, method: str, params: dict) -> dict:
    """
    POST a JSON-RPC call to the Midnight node.
    Raises on HTTP error or non-200 response.
    """
    url = base_url.rstrip("/") + "/rpc"
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Midnight RPC error: {data['error']}")
    return data.get("result", {})
