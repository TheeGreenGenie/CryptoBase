from functools import wraps

from flask import Blueprint, g, jsonify, request, session

from app.extensions import csrf, db, limiter
from app.models import APIKey, Position, User
from app.services import lending as lending_service
from app.services.api_keys import generate_raw_api_key, hash_api_key, normalize_scopes, touch_api_key, verify_api_key
from app.services.pricing import get_supported_assets
from app.services.risk import portfolio_summary
from app.utils import login_required

api_bp = Blueprint("api", __name__)


def require_api_scope(scope):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            raw_key = request.headers.get("X-API-Key", "")
            if not raw_key:
                return fail("unauthorized", "Missing API key", 401)
            for api_key in APIKey.query.filter_by(is_active=True).all():
                if verify_api_key(raw_key, api_key):
                    if scope not in api_key.scopes:
                        return fail("forbidden", "API key does not have the required scope", 403)
                    touch_api_key(api_key)
                    db.session.commit()
                    g.api_key = api_key
                    return view(*args, **kwargs)
            return fail("unauthorized", "Invalid or revoked API key", 401)

        return wrapped

    return decorator


def ok(data, status=200):
    return jsonify({"ok": True, "data": data, "error": None}), status


def fail(code, message, status):
    return jsonify({"ok": False, "data": None, "error": {"code": code, "message": message}}), status


@api_bp.get("/health")
def health():
    return ok({"status": "healthy"})


@api_bp.get("/positions")
@limiter.limit("60/minute")
@require_api_scope("read:positions")
def positions():
    rows = Position.query.filter_by(user_id=g.api_key.user_id).all()
    return ok(
        [
            {
                "asset_symbol": row.asset_symbol,
                "position_type": row.position_type,
                "amount_raw": row.amount_raw,
                "amount_decimal": str(row.amount_decimal),
                "usd_value": str(row.usd_value),
            }
            for row in rows
        ]
    )


@api_bp.get("/risk")
@limiter.limit("60/minute")
@require_api_scope("read:risk")
def risk():
    return ok(portfolio_summary(g.api_key.user_id))


@api_bp.get("/yield-opportunities")
@limiter.limit("60/minute")
@require_api_scope("read:opportunities")
def yield_opportunities():
    assets = get_supported_assets()
    return ok(
        [
            {"asset": asset["symbol"], "apy": "demo", "chain_id": request.args.get("chain_id", "31337")}
            for asset in assets
        ]
    )


@api_bp.post("/actions/build")
@csrf.exempt
@limiter.limit("60/minute")
@require_api_scope("write:actions")
def build_action():
    payload = request.get_json(silent=True) or {}
    user = User.query.get(g.api_key.user_id)
    action = payload.get("action")
    amount = payload.get("amount")
    builders = {
        "supply": lending_service.build_supply_tx,
        "withdraw": lending_service.build_withdraw_tx,
        "borrow": lending_service.build_borrow_tx,
        "repay": lending_service.build_repay_tx,
    }
    if action not in builders:
        return fail("validation_error", "Unsupported action", 400)
    try:
        tx = builders[action](user.wallet_address, amount)
    except ValueError as exc:
        return fail("validation_error", str(exc), 400)
    except Exception as exc:
        return fail("internal_error", str(exc), 500)
    return ok({"tx": tx, "signed": False})


@api_bp.post("/api-keys")
@csrf.exempt
@login_required
def create_api_key():
    payload = request.get_json(silent=True) or {}
    label = (payload.get("label") or "").strip()
    if not label:
        return fail("validation_error", "API key label is required", 400)
    try:
        scopes = normalize_scopes(payload.get("scopes"))
    except ValueError as exc:
        return fail("validation_error", str(exc), 400)

    raw_key = generate_raw_api_key()
    api_key = APIKey(user_id=session["user_id"], label=label, scopes=scopes, key_hash=hash_api_key(raw_key))
    db.session.add(api_key)
    db.session.commit()
    return ok({"id": api_key.id, "label": api_key.label, "scopes": api_key.scopes, "api_key": raw_key}, 201)


@api_bp.get("/api-keys")
@login_required
def list_api_keys():
    keys = APIKey.query.filter_by(user_id=session["user_id"]).order_by(APIKey.created_at.desc()).all()
    return ok(
        [
            {
                "id": key.id,
                "label": key.label,
                "scopes": key.scopes,
                "is_active": key.is_active,
                "created_at": key.created_at.isoformat(),
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            }
            for key in keys
        ]
    )


@api_bp.delete("/api-keys/<int:key_id>")
@csrf.exempt
@login_required
def revoke_api_key(key_id):
    api_key = APIKey.query.filter_by(id=key_id, user_id=session["user_id"]).one_or_none()
    if api_key is None:
        return fail("validation_error", "API key not found", 404)
    api_key.is_active = False
    db.session.commit()
    return ok({"id": api_key.id, "is_active": False})
