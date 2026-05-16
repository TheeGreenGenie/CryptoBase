from datetime import datetime, timezone

from app.extensions import db


class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    chain_id = db.Column(db.Integer, nullable=False, index=True)
    trade_type = db.Column(db.String(32), nullable=False)
    token_in = db.Column(db.String(42), nullable=False)
    token_out = db.Column(db.String(42), nullable=False)
    amount_in_raw = db.Column(db.String(96), nullable=False)
    min_amount_out_raw = db.Column(db.String(96), nullable=True)
    quoted_amount_out_raw = db.Column(db.String(96), nullable=True)
    slippage_bps = db.Column(db.Integer, nullable=False, default=50)
    status = db.Column(db.String(32), nullable=False, default="quoted", index=True)
    tx_hash = db.Column(db.String(66), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="trades")
