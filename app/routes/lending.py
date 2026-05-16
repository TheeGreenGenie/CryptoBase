import traceback

from flask import Blueprint, current_app, jsonify, render_template, request, session

from app.extensions import csrf
from app.services import lending as lending_service
from app.utils import current_wallet_address, login_required

lending_bp = Blueprint("lending", __name__)


@lending_bp.get("/")
def index():
    from app.services.lending import _collateral_tokens
    return render_template("lending/index.html", collateral_tokens=_collateral_tokens())


@lending_bp.post("/supply/build-tx")
@csrf.exempt
@login_required
def supply_build_tx():
    return _build_lending_tx(lending_service.build_supply_tx, use_token=True)


@lending_bp.post("/withdraw/build-tx")
@csrf.exempt
@login_required
def withdraw_build_tx():
    return _build_lending_tx(lending_service.build_withdraw_tx, use_token=True)


@lending_bp.post("/borrow/build-tx")
@csrf.exempt
@login_required
def borrow_build_tx():
    return _build_lending_tx(lending_service.build_borrow_tx)


@lending_bp.post("/repay/build-tx")
@csrf.exempt
@login_required
def repay_build_tx():
    return _build_lending_tx(lending_service.build_repay_tx)


@lending_bp.post("/tx-submitted")
@csrf.exempt
@login_required
def tx_submitted():
    payload = request.get_json(silent=True) or {}
    tx_hash = payload.get("tx_hash")
    action = payload.get("action")
    if not tx_hash or not action:
        return (
            jsonify(
                {
                    "ok": False,
                    "data": None,
                    "error": {"code": "validation_error", "message": "tx_hash and action are required"},
                }
            ),
            400,
        )

    pending = session.setdefault("pending_lending_txs", [])
    pending.append({"tx_hash": tx_hash, "action": action})
    session.modified = True
    return jsonify({"ok": True, "data": {"tracked": True, "tx_hash": tx_hash}, "error": None})


@lending_bp.get("/positions/partial")
@login_required
def positions_partial():
    position = None
    error = None
    try:
        position = lending_service.read_position(current_wallet_address())
    except Exception as exc:
        error = str(exc)
        current_app.logger.error("positions_partial failed:\n%s", traceback.format_exc())
    return render_template("lending/_position_table.html", position=position, error=error)


@lending_bp.get("/debug/contracts")
def debug_contracts():
    """Diagnostic endpoint — remove before production."""
    from app.services.blockchain import checksum, get_web3, load_abi

    w3 = get_web3()
    results = {
        "connected": w3.is_connected(),
        "chain_id": w3.eth.chain_id,
        "wallet_in_session": session.get("wallet_address"),
        "contracts": {},
        "calls": {},
        "errors": {},
    }

    addr_keys = [
        ("LENDING_POOL_ADDRESS", "LendingPool"),
        ("DEBT_TOKEN_ADDRESS", "ERC20"),
        ("PRICE_ORACLE_ADDRESS", "MockPriceOracle"),
    ]

    for config_key, abi_name in addr_keys:
        addr = current_app.config.get(config_key, "")
        results["contracts"][config_key] = addr
        if not addr:
            results["errors"][config_key] = "NOT SET in config"
            continue
        try:
            code_len = len(w3.eth.get_code(checksum(addr)))
            results["contracts"][config_key + "_bytecode_len"] = code_len
            if code_len == 0:
                results["errors"][config_key] = "NO BYTECODE — contract not deployed at this address"
        except Exception as e:
            results["errors"][config_key] = f"checksum/code check failed: {e}"

    # Try the actual read_position calls
    wallet = session.get("wallet_address") or "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    try:
        pool_addr = current_app.config.get("LENDING_POOL_ADDRESS", "")
        pool = w3.eth.contract(address=checksum(pool_addr), abi=load_abi("LendingPool"))
        results["calls"]["collateralBalance"] = str(pool.functions.collateralBalance(checksum(wallet)).call())
        results["calls"]["debtBalance"] = str(pool.functions.debtBalance(checksum(wallet)).call())
        results["calls"]["healthFactor"] = str(pool.functions.healthFactor(checksum(wallet)).call())
    except Exception as e:
        results["errors"]["contract_calls"] = traceback.format_exc()

    return jsonify(results)


def _build_lending_tx(builder, use_token: bool = False):
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount")
    if not amount:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "Amount is required"}}
            ),
            400,
        )
    try:
        if use_token:
            token = payload.get("token", "0x0000000000000000000000000000000000000000")
            result = builder(current_wallet_address(), amount, token)
        else:
            result = builder(current_wallet_address(), amount)
    except ValueError as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "validation_error", "message": str(exc)}}), 400
    except Exception as exc:
        return jsonify({"ok": False, "data": None, "error": {"code": "internal_error", "message": str(exc)}}), 500
    return jsonify({"ok": True, "data": result, "error": None})
