from datetime import datetime, timezone

from app.extensions import db


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    chain_id = db.Column(db.Integer, nullable=False, index=True)
    collateral_asset = db.Column(db.String(42), nullable=False)
    debt_asset = db.Column(db.String(42), nullable=False)
    collateral_amount_raw = db.Column(db.String(96), nullable=False, default="0")
    debt_amount_raw = db.Column(db.String(96), nullable=False, default="0")
    health_factor = db.Column(db.Numeric(38, 18), nullable=True)
    ltv_bps = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="active", index=True)
    opened_tx_hash = db.Column(db.String(66), nullable=True)
    closed_tx_hash = db.Column(db.String(66), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="loans")
