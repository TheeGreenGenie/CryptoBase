from app import create_app
from app.extensions import make_celery
from app.services import monitoring  # noqa: F401

flask_app = create_app()
celery = make_celery(flask_app)
celery.conf.beat_schedule = {
    "sync-active-positions-every-minute": {
        "task": "monitoring.sync_active_positions",
        "schedule": 60.0,
    },
    "check-risk-alerts-every-minute": {
        "task": "monitoring.check_risk_alerts",
        "schedule": 60.0,
    },
    "evaluate-agent-suggestions-every-five-minutes": {
        "task": "monitoring.evaluate_agent_suggestions",
        "schedule": 300.0,
    },
}
