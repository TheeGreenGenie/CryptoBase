import threading

from flask import Blueprint, current_app, jsonify, render_template, request, session

from app.extensions import csrf, db
from app.models import AgentSuggestion, User
from app.services.agent import generate_and_cache_suggestions, generate_rule_suggestions
from app.utils import login_required

agent_bp = Blueprint("agent", __name__)


@agent_bp.get("/")
@login_required
def index():
    user = User.query.get(session["user_id"])
    suggestions = AgentSuggestion.query.filter_by(user_id=user.id).order_by(AgentSuggestion.created_at.desc()).all()
    return render_template("agent/index.html", user=user, suggestions=suggestions)


@agent_bp.get("/suggestions/partial")
@login_required
def suggestions_partial():
    suggestions = AgentSuggestion.query.filter_by(user_id=session["user_id"]).order_by(AgentSuggestion.created_at.desc()).all()
    return render_template("agent/_suggestions.html", suggestions=suggestions)


@agent_bp.post("/preferences")
@csrf.exempt
@login_required
def save_preferences():
    payload = request.get_json(silent=True) or {}
    user = User.query.get(session["user_id"])
    risk_tolerance = payload.get("risk_tolerance", user.risk_tolerance)
    if risk_tolerance not in {"conservative", "moderate", "aggressive"}:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "Invalid risk tolerance"}}
            ),
            400,
        )

    user.risk_tolerance = risk_tolerance
    user.max_exposure_usd = payload.get("max_exposure_usd") or None
    user.preferred_assets = payload.get("preferred_assets") or []
    db.session.commit()
    return jsonify({"ok": True, "data": {"saved": True}, "error": None})


@agent_bp.post("/suggestions/generate")
@csrf.exempt
@login_required
def generate_suggestions():
    user = User.query.get(session["user_id"])
    app = current_app._get_current_object()
    user_id = user.id

    # Save rule-based suggestions immediately so the UI has something to show
    rule_suggestions = generate_rule_suggestions(user)
    for s in rule_suggestions:
        db.session.add(s)
    db.session.commit()

    # Quick availability check so the UI knows whether to show the pending spinner
    from app.services.agent import _llm_is_available
    llm_available = _llm_is_available()

    # Cache lookup + LLM loop runs in background (can take up to 60 s per call)
    def _run():
        with app.app_context():
            u = User.query.get(user_id)
            if u is None:
                return
            try:
                generate_and_cache_suggestions(u)
            except Exception as exc:
                current_app.logger.error("Background suggestion generation failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({
        "ok": True,
        "data": {"created": len(rule_suggestions), "llm_pending": llm_available},
        "error": None,
    })


@agent_bp.post("/suggestions/<int:suggestion_id>/approve")
@csrf.exempt
@login_required
def approve_suggestion(suggestion_id):
    suggestion = _owned_suggestion(suggestion_id)
    if suggestion is None:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "Suggestion not found"}}
            ),
            404,
        )
    suggestion.status = "approved"
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": suggestion.id, "status": suggestion.status}, "error": None})


@agent_bp.post("/suggestions/<int:suggestion_id>/reject")
@csrf.exempt
@login_required
def reject_suggestion(suggestion_id):
    suggestion = _owned_suggestion(suggestion_id)
    if suggestion is None:
        return (
            jsonify(
                {"ok": False, "data": None, "error": {"code": "validation_error", "message": "Suggestion not found"}}
            ),
            404,
        )
    suggestion.status = "rejected"
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": suggestion.id, "status": suggestion.status}, "error": None})


def _owned_suggestion(suggestion_id):
    return AgentSuggestion.query.filter_by(id=suggestion_id, user_id=session["user_id"]).one_or_none()
