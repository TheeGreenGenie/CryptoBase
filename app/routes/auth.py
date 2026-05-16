from datetime import datetime, timedelta, timezone
import secrets

from eth_account import Account
from eth_account.messages import encode_defunct
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from app.extensions import csrf, db
from app.models import User
from app.utils import login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/connect")
def connect():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    return render_template("auth/connect.html")


@auth_bp.post("/nonce")
@csrf.exempt
def nonce():
    payload = request.get_json(silent=True) or {}
    address = (payload.get("address") or "").strip()
    chain_id = int(payload.get("chain_id") or current_app.config["CHAIN_ID"])

    if not address:
        return (
            jsonify(
                {
                    "ok": False,
                    "data": None,
                    "error": {"code": "validation_error", "message": "Wallet address is required"},
                }
            ),
            400,
        )

    nonce_value = secrets.token_urlsafe(24)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=10)
    domain = request.host
    uri = request.url_root.rstrip("/")

    message = "\n".join(
        [
            f"{domain} wants you to sign in with your Ethereum account:",
            address,
            "",
            "Sign in to CryptoBase.",
            "",
            f"URI: {uri}",
            "Version: 1",
            f"Chain ID: {chain_id}",
            f"Nonce: {nonce_value}",
            f"Issued At: {issued_at.isoformat()}",
        ]
    )

    session["siwe_nonce"] = nonce_value
    session["siwe_address"] = address.lower()
    session["siwe_chain_id"] = chain_id
    session["siwe_expires_at"] = expires_at.isoformat()

    return jsonify(
        {
            "ok": True,
            "data": {
                "nonce": nonce_value,
                "message": message,
                "expires_at": expires_at.isoformat(),
            },
            "error": None,
        }
    )


@auth_bp.post("/verify")
@csrf.exempt
def verify():
    payload = request.get_json(silent=True) or {}
    address = (payload.get("address") or "").strip().lower()
    message = payload.get("message") or ""
    signature = payload.get("signature") or ""
    email = (payload.get("email") or "").strip() or None

    if not address or not message or not signature:
        return (
            jsonify(
                {
                    "ok": False,
                    "data": None,
                    "error": {"code": "validation_error", "message": "Address, message, and signature are required"},
                }
            ),
            400,
        )

    expected_nonce = session.get("siwe_nonce")
    expected_address = session.get("siwe_address")
    expires_at_raw = session.get("siwe_expires_at")

    if not expected_nonce or not expected_address or not expires_at_raw:
        return (
            jsonify({"ok": False, "data": None, "error": {"code": "unauthorized", "message": "Missing SIWE nonce"}}),
            401,
        )

    expires_at = datetime.fromisoformat(expires_at_raw)
    if datetime.now(timezone.utc) > expires_at:
        clear_siwe_session()
        return (
            jsonify({"ok": False, "data": None, "error": {"code": "unauthorized", "message": "SIWE nonce expired"}}),
            401,
        )

    if address != expected_address or f"Nonce: {expected_nonce}" not in message or not message.startswith(request.host):
        return (
            jsonify({"ok": False, "data": None, "error": {"code": "unauthorized", "message": "SIWE message mismatch"}}),
            401,
        )

    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature).lower()
    except Exception:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "unauthorized", "message": "Invalid wallet signature"}}
            ),
            401,
        )

    if recovered != address:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "unauthorized", "message": "Invalid wallet signature"}}
            ),
            401,
        )

    user = User.query.filter_by(wallet_address=address).one_or_none()
    if user is None:
        user = User(wallet_address=address, email=email)
        db.session.add(user)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    session.permanent = True
    session["user_id"] = user.id
    session["wallet_address"] = user.wallet_address
    clear_siwe_session()

    return jsonify({"ok": True, "data": {"wallet_address": user.wallet_address}, "error": None})


@auth_bp.post("/logout")
@csrf.exempt
def logout():
    session.clear()
    return jsonify({"ok": True, "data": {"logged_out": True}, "error": None})


@auth_bp.get("/me")
@login_required
def me():
    user = User.query.get(session["user_id"])
    return jsonify({
        "ok": True,
        "data": {
            "wallet_address": user.wallet_address,
            "email": user.email,
            "risk_tolerance": user.risk_tolerance,
            "max_exposure_usd": str(user.max_exposure_usd) if user.max_exposure_usd else None,
            "preferred_assets": user.preferred_assets,
            "reputation_score": user.reputation_score,
            "kyc_status": user.kyc_status,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        },
        "error": None,
    })


@auth_bp.get("/profile")
@login_required
def profile():
    user = User.query.get(session["user_id"])
    return render_template("auth/profile.html", user=user)


@auth_bp.post("/profile")
@csrf.exempt
@login_required
def update_profile():
    payload = request.get_json(silent=True) or {}
    user = User.query.get(session["user_id"])
    email = (payload.get("email") or "").strip() or None
    user.email = email
    db.session.commit()
    return jsonify({"ok": True, "data": {"saved": True}, "error": None})


def clear_siwe_session():
    session.pop("siwe_nonce", None)
    session.pop("siwe_address", None)
    session.pop("siwe_chain_id", None)
    session.pop("siwe_expires_at", None)
