import os
import logging
from datetime import datetime, timedelta

from flask import Flask, request, session, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Data retention period (7 days)
app.config["DATA_RETENTION_DAYS"] = 7

# initialize the app with the extension
db.init_app(app)


@app.before_request
def before_request():
    g.request_start_time = datetime.now()


@app.after_request
def after_request(response):
    # Log request details
    if hasattr(g, 'request_start_time'):
        request_duration = datetime.now() - g.request_start_time
        logger.info(
            f"Request: {request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {request_duration.total_seconds():.4f}s"
        )
    return response


@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    def now():
        return datetime.now()
    
    return dict(now=now)


@app.cli.command("cleanup-logs")
def cleanup_logs():
    """Clean up logs older than the retention period."""
    with app.app_context():
        from models import Transaction, ErrorLog
        retention_days = app.config["DATA_RETENTION_DAYS"]
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_transactions = Transaction.query.filter(
            Transaction.created_at < cutoff_date
        ).delete()
        
        deleted_logs = ErrorLog.query.filter(
            ErrorLog.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        logger.info(f"Cleaned up {deleted_transactions} transactions and {deleted_logs} error logs older than {retention_days} days.")


with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    
    # Import routes after models
    import routes  # noqa: F401
