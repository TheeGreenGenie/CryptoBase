from flask import Blueprint, jsonify, render_template, request, session

from app.extensions import csrf, db
from app.models import Trade
from app.services import trading as trading_service
from app.utils import current_wallet_address, login_required

trading_bp = Blueprint("trading", __name__)


@trading_bp.get("/")
def index():
    return render_template("trading/index.html")


@trading_bp.post("/quote")
@csrf.exempt
def quote():
    payload = request.get_json(silent=True) or {}
    try:
        quote_data = trading_service.quote_swap(
            payload.get("token_in", ""),
            payload.get("token_out", ""),
            payload.get("amount", "0"),
            int(payload.get("slippage_bps", 50)),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "validation_error", "message": str(exc)}}), 400
    return jsonify({"ok": True, "data": quote_data, "error": None})


@trading_bp.post("/swap/build-tx")
@csrf.exempt
@login_required
def swap_build_tx():
    payload = request.get_json(silent=True) or {}
    try:
        tx = trading_service.build_swap_tx(
            current_wallet_address(),
            payload.get("token_in", ""),
            payload.get("token_out", ""),
            payload.get("amount", "0"),
            int(payload.get("slippage_bps", 50)),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "validation_error", "message": str(exc)}}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "quote_unavailable", "message": str(exc)}}), 409
    return jsonify({"ok": True, "data": {"tx": tx}, "error": None})


@trading_bp.post("/limit-orders")
@csrf.exempt
@login_required
def create_limit_order():
    payload = request.get_json(silent=True) or {}
    try:
        quote_data = trading_service.quote_swap(
            payload.get("token_in", ""),
            payload.get("token_out", ""),
            payload.get("amount", "0"),
            int(payload.get("slippage_bps", 50)),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "validation_error", "message": str(exc)}}), 400
    trade = Trade(
        user_id=session["user_id"],
        chain_id=int(current_app_config("CHAIN_ID")),
        trade_type="limit_order",
        token_in=quote_data["token_in"],
        token_out=quote_data["token_out"],
        amount_in_raw=quote_data["amount_in"],
        min_amount_out_raw=quote_data["min_amount_out"],
        quoted_amount_out_raw=quote_data["quoted_amount_out"],
        slippage_bps=quote_data["slippage_bps"],
        status="quoted",
    )
    db.session.add(trade)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": trade.id, "status": trade.status}, "error": None})


@trading_bp.post("/limit-orders/<int:trade_id>/cancel")
@csrf.exempt
@login_required
def cancel_limit_order(trade_id):
    trade = Trade.query.filter_by(id=trade_id, user_id=session["user_id"], trade_type="limit_order").one_or_none()
    if trade is None:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "Limit order not found"}}
            ),
            404,
        )
    trade.status = "cancelled"
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": trade.id, "status": trade.status}, "error": None})


@trading_bp.post("/tx-submitted")
@csrf.exempt
@login_required
def tx_submitted():
    payload = request.get_json(silent=True) or {}
    tx_hash = payload.get("tx_hash")
    if not tx_hash:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "tx_hash is required"}}
            ),
            400,
        )
    return jsonify({"ok": True, "data": {"tracked": True, "tx_hash": tx_hash}, "error": None})


def current_app_config(key):
    from flask import current_app

    return current_app.config[key]
