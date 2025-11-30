from flask import Flask
from fin_server.routes.auth import auth_bp
from fin_server.routes.user import user_bp
from fin_server.routes.task import task_bp
from fin_server.security.authentication import AuthSecurity

app = Flask(__name__)

# Set your JWT secret key here (use a secure random string in production)
AuthSecurity.configure(secret_key="your-very-secret-key", algorithm="HS256", access_token_expire_minutes=60, refresh_token_expire_days=7)

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(task_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
