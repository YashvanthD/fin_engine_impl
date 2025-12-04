from flask import Flask
from flask_cors import CORS
from fin_server.routes.auth import auth_bp
from fin_server.routes.user import user_bp
from fin_server.routes.task import task_bp
from fin_server.routes.company import company_bp
from fin_server.security.authentication import AuthSecurity
from fin_server.notification.scheduler import TaskScheduler
import logging

app = Flask(__name__)
CORS(app)

# Set your JWT secret key here (use a secure random string in production)
AuthSecurity.configure(secret_key="your-very-secret-key", algorithm="HS256", access_token_expire_minutes=60, refresh_token_expire_days=7)

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(task_bp)
app.register_blueprint(company_bp)

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    scheduler = TaskScheduler(interval_seconds=60)
    scheduler.start()
    app.run(host="0.0.0.0", port=8001, debug=True)
