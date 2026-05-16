import traceback

from flask import Blueprint, current_app, jsonify

from app.extensions import csrf
from app.services import faucet as faucet_service
from app.utils import current_wallet_address, login_required

faucet_bp = Blueprint("faucet", __name__)


@faucet_bp.post("/drip")
@csrf.exempt
@login_required
def drip():
    try:
        tx_hash = faucet_service.drip(current_wallet_address())
        amount = current_app.config["FAUCET_AMOUNT"]
        return jsonify({"ok": True, "data": {"tx_hash": tx_hash, "amount": amount}, "error": None})
    except Exception as exc:
        current_app.logger.error("Faucet drip failed:\n%s", traceback.format_exc())
        return jsonify({"ok": False, "data": None, "error": {"code": "faucet_error", "message": str(exc)}}), 500
