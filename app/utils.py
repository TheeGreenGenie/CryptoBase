from functools import wraps

from flask import jsonify, redirect, request, session, url_for


def wants_json_response():
    return (
        request.path.startswith("/api/")
        or request.headers.get("HX-Request") == "true"
        or request.accept_mimetypes.best == "application/json"
    )


def current_wallet_address():
    return session.get("wallet_address")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id"):
            return view(*args, **kwargs)
        if wants_json_response():
            return (
                jsonify(
                    {"ok": False, "data": None, "error": {"code": "unauthorized", "message": "Authentication required"}}
                ),
                401,
            )
        return redirect(url_for("auth.connect"))

    return wrapped
