from app.routes.agent import agent_bp
from app.routes.api import api_bp
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.faucet import faucet_bp
from app.routes.lending import lending_bp
from app.routes.midnight import midnight_bp
from app.routes.trading import trading_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(faucet_bp, url_prefix="/faucet")
    app.register_blueprint(lending_bp, url_prefix="/lending")
    app.register_blueprint(trading_bp, url_prefix="/trading")
    app.register_blueprint(agent_bp, url_prefix="/agent")
    app.register_blueprint(midnight_bp, url_prefix="/privacy")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
