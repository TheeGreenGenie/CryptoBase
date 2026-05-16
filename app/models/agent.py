import hashlib
from datetime import datetime, timezone

from app.extensions import db

# Suggestion types that are safe to share with any user (won't cause loss)
SHAREABLE_TYPES = {"hold", "supply", "borrow", "swap"}


class SuggestionCache(db.Model):
    """Shared pool of LLM-generated suggestions deduplicated by content hash.
    Safe (low/medium, non-repay) entries are shown to other users who haven't seen them."""

    __tablename__ = "suggestion_cache"

    id = db.Column(db.Integer, primary_key=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    suggestion_type = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    recommended_action = db.Column(db.JSON, nullable=False, default=dict)
    risk_level = db.Column(db.String(32), nullable=False, default="medium")
    source = db.Column(db.String(32), nullable=False, default="llm")
    is_shareable = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def make_hash(suggestion_type: str, title: str, rationale: str) -> str:
        raw = f"{suggestion_type}|{title.strip().lower()}|{rationale.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def is_safe_to_share(suggestion_type: str, risk_level: str) -> bool:
        return suggestion_type in SHAREABLE_TYPES and risk_level in {"low", "medium"}


class AgentSuggestion(db.Model):
    __tablename__ = "agent_suggestions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    suggestion_type = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    recommended_action = db.Column(db.JSON, nullable=False, default=dict)
    risk_level = db.Column(db.String(32), nullable=False, default="medium")
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    source = db.Column(db.String(32), nullable=False, default="rules")
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cache_id = db.Column(db.Integer, db.ForeignKey("suggestion_cache.id"), nullable=True, index=True)
    approval_tx_hash = db.Column(db.String(66), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="suggestions")
