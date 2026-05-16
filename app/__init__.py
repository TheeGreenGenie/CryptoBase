import logging

from flask import Flask, jsonify, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.config import get_config
from app.extensions import csrf, db, limiter, migrate
from app.routes import register_blueprints


@event.listens_for(Engine, "connect")
def _set_sqlite_wal(dbapi_conn, _record):
    """Enable WAL mode on every new SQLite connection so background threads can write
    without blocking readers (and vice-versa)."""
    try:
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass  # non-SQLite databases ignore this silently


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or get_config())

    configure_logging(app)
    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_healthcheck(app)

    return app


def configure_logging(app):
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html", error=error), 400

    @app.errorhandler(401)
    def unauthenticated(error):
        return render_template("errors/400.html", error=error), 401

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html", error=error), 404

    @app.errorhandler(429)
    def rate_limited(error):
        return render_template("errors/400.html", error=error), 429

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        return render_template("errors/500.html", error=error), 500


def register_healthcheck(app):
    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "data": {"status": "healthy"}, "error": None})
