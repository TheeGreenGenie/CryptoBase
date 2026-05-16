from datetime import datetime, timezone

from app.extensions import db


class Position(db.Model):
    __tablename__ = "positions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    chain_id = db.Column(db.Integer, nullable=False, index=True)
    asset_address = db.Column(db.String(42), nullable=False)
    asset_symbol = db.Column(db.String(32), nullable=False)
    position_type = db.Column(db.String(32), nullable=False)
    amount_raw = db.Column(db.String(96), nullable=False, default="0")
    amount_decimal = db.Column(db.Numeric(38, 18), nullable=False, default=0)
    usd_value = db.Column(db.Numeric(20, 2), nullable=False, default=0)
    last_synced_block = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="positions")
