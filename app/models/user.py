from datetime import datetime, timezone

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    reputation_score = db.Column(db.Integer, nullable=False, default=0)
    kyc_status = db.Column(db.String(32), nullable=False, default="not_started")
    risk_tolerance = db.Column(db.String(32), nullable=False, default="moderate")
    max_exposure_usd = db.Column(db.Numeric(20, 2), nullable=True)
    preferred_assets = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    positions = db.relationship("Position", back_populates="user", cascade="all, delete-orphan")
    loans = db.relationship("Loan", back_populates="user", cascade="all, delete-orphan")
    trades = db.relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    suggestions = db.relationship("AgentSuggestion", back_populates="user", cascade="all, delete-orphan")
    api_keys = db.relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.wallet_address}>"
