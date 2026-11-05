"""Electricity Regulator backend (Flask).

- /api/...  REST API (JSON, bearer token) used by the Flutter app (SRS 7.4.3)
- /...      the same features as web pages, for demonstrations in any browser
"""
from __future__ import annotations

import os
import secrets

from flask import Flask

from . import db as dbmod
from .format import register_filters


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(16),
        DATABASE=os.environ.get("DATABASE") or os.path.join(app.instance_path, "electricity_regulator.sqlite"),
        FETCH_WEATHER=os.environ.get("FETCH_WEATHER", "1") == "1",
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if os.environ.get("BEHIND_PROXY") == "1":
        # On Render (or any host with an HTTPS proxy), trust the proxy's headers so links use https://.
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    os.makedirs(app.instance_path, exist_ok=True)

    with app.app_context():
        conn = dbmod.connect(app.config["DATABASE"])
        dbmod.init_db(conn)
        conn.close()
    app.teardown_appcontext(dbmod.close_db)
    register_filters(app)

    from .api import bp as api_bp
    from .web import bp as web_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)
    return app
