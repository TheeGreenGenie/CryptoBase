from decimal import Decimal

from app.models import Loan, Position

LIQUIDATION_THRESHOLD_BPS = 12_500


def calculate_health_factor(collateral_usd, debt_usd, liquidation_threshold_bps=LIQUIDATION_THRESHOLD_BPS):
    collateral = Decimal(str(collateral_usd))
    debt = Decimal(str(debt_usd))
    if debt == 0:
        return Decimal("999999999")
    if collateral == 0:
        return Decimal("0")
    threshold = Decimal(liquidation_threshold_bps) / Decimal(10_000)
    return (collateral * threshold) / debt


def classify_health_factor(health_factor):
    value = Decimal(str(health_factor))
    if value >= Decimal("1.6"):
        return "healthy"
    if value >= Decimal("1.3"):
        return "watch"
    if value >= Decimal("1.1"):
        return "danger"
    return "liquidatable"


def build_risk_alert(user, loan_or_position):
    health_factor = getattr(loan_or_position, "health_factor", None)
    if health_factor is None:
        return None
    risk_class = classify_health_factor(health_factor)
    if risk_class == "healthy":
        return None
    return {
        "user_id": user.id,
        "risk_class": risk_class,
        "message": f"Position health factor is {health_factor}; current risk class is {risk_class}.",
    }


def portfolio_summary(user_id):
    positions = Position.query.filter_by(user_id=user_id).all()
    loans = Loan.query.filter_by(user_id=user_id, status="active").all()
    collateral_usd = sum(Decimal(str(p.usd_value)) for p in positions if p.position_type == "collateral")
    debt_usd = sum(Decimal(str(p.usd_value)) for p in positions if p.position_type == "debt")
    health_factor = calculate_health_factor(collateral_usd, debt_usd)
    return {
        "collateral_usd": str(collateral_usd),
        "debt_usd": str(debt_usd),
        "health_factor": str(health_factor),
        "risk_class": classify_health_factor(health_factor),
        "active_loan_count": len(loans),
    }
