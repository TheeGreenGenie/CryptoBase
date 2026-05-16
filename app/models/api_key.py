from datetime import datetime, timezone

from app.extensions import db

DEFAULT_SCOPES = ["read:positions", "read:risk", "read:opportunities"]


class APIKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    key_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    label = db.Column(db.String(120), nullable=False)
    scopes = db.Column(db.JSON, nullable=False, default=lambda: list(DEFAULT_SCOPES))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="api_keys")
