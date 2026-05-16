import traceback

from flask import Blueprint, current_app, render_template, session

from app.services import lending as lending_service
from app.services.risk import classify_health_factor
from app.utils import current_wallet_address, login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def index():
    return render_template("dashboard.html")


@dashboard_bp.get("/metrics/partial")
def metrics_partial():
    wallet = session.get("wallet_address")
    collateral_usd, debt_usd, health_factor, risk_class = "0.00", "0.00", "--", "healthy"
    if wallet:
        try:
            pos = lending_service.read_position(wallet)
            collateral_usd = pos["collateral_usd"]
            debt_usd = pos["debt_usd"]
            hf_raw = int(pos["health_factor_raw"])
            if hf_raw > 0:
                hf = hf_raw / 1e18
                health_factor = f"{hf:.2f}"
                risk_class = classify_health_factor(hf)
        except Exception:
            current_app.logger.error("metrics_partial failed:\n%s", traceback.format_exc())
    return render_template(
        "partials/_metrics.html",
        collateral_usd=collateral_usd,
        debt_usd=debt_usd,
        health_factor=health_factor,
        risk_class=risk_class,
    )


@dashboard_bp.get("/risk/partial")
def risk_partial():
    wallet = session.get("wallet_address")
    summary = None
    if wallet:
        try:
            pos = lending_service.read_position(wallet)
            collateral_usd = float(pos["collateral_usd"])
            debt_usd = float(pos["debt_usd"])
            hf_raw = int(pos["health_factor_raw"])
            hf = hf_raw / 1e18 if hf_raw > 0 else 0
            summary = {
                "collateral_usd": pos["collateral_usd"],
                "debt_usd": pos["debt_usd"],
                "health_factor": f"{hf:.2f}" if hf > 0 else "--",
                "risk_class": classify_health_factor(hf) if debt_usd > 0 else "healthy",
            }
        except Exception:
            current_app.logger.error("risk_partial failed:\n%s", traceback.format_exc())
    return render_template("partials/_risk_summary.html", summary=summary)
