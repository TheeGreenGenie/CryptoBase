from flask import Blueprint, jsonify, render_template, session

from app.extensions import csrf
from app.services import midnight_service
from app.services import lending as lending_service
from app.utils import login_required

midnight_bp = Blueprint("midnight", __name__, template_folder="../templates")


@midnight_bp.get("/")
@login_required
def index():
    wallet = session.get("wallet_address", "")
    user_id = session.get("user_id")
    attestation = midnight_service.attest_position(wallet, user_id)
    return render_template("midnight/index.html", attestation=attestation, wallet=wallet)


@midnight_bp.post("/attest")
@csrf.exempt
@login_required
def attest():
    wallet = session.get("wallet_address", "")
    user_id = session.get("user_id")
    try:
        result = midnight_service.attest_position(wallet, user_id)
        return jsonify({"ok": True, "data": result, "error": None})
    except Exception as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "attestation_error", "message": str(exc)}}), 500


@midnight_bp.get("/verify/<wallet_address>")
def verify(wallet_address: str):
    attestation = midnight_service.get_public_attestation(wallet_address)
    return render_template("midnight/verify.html", attestation=attestation, wallet=wallet_address)


@midnight_bp.get("/shield/partial")
@login_required
def shield_partial():
    wallet = session.get("wallet_address", "")
    user_id = session.get("user_id")
    attestation = midnight_service.get_public_attestation(wallet, user_id)
    return render_template("partials/_midnight_shield.html", attestation=attestation, wallet=wallet)


@midnight_bp.get("/my-amounts")
@login_required
def my_amounts():
    wallet = session.get("wallet_address", "")
    try:
        pos = lending_service.read_position(wallet)
    except Exception:
        pos = None
    return render_template("partials/_my_amounts.html", position=pos)


@midnight_bp.get("/my-amounts-json")
@login_required
def my_amounts_json():
    """
    Returns the authenticated user's position amounts as JSON.
    Only their session can call this. Never exposed in the public API.
    """
    wallet = session.get("wallet_address", "")
    try:
        pos = lending_service.read_position(wallet)
        return jsonify({"ok": True, "data": pos})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
