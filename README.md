# fin_engine_impl

Backend service for aquaculture/pond management, built with Flask, Flask-SocketIO and MongoDB.

## Quick start (development)

```bash
cd /Users/ydevaraju/PycharmProjects/PythonProject1/4/fin_engine_impl
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="user_db"
export JWT_SECRET="change-me-in-prod"
export FLASK_DEBUG="true"

# Run the server (defaults to port 5000)
python server.py
```

Then open http://localhost:5000/ to see the API documentation page.

## Health check

A lightweight health endpoint is available at:

- `GET /public/health`  returns 200 with `{ "status": "ok", "db": "reachable" }` when the API and database are healthy.

## Environment variables

- `MONGO_URI`  MongoDB connection string (required in production, defaults to `mongodb://localhost:27017` for dev).
- `MONGO_DB`  MongoDB database name (default: `user_db`).
- `JWT_SECRET`  secret key for signing JWTs (required).
- `JWT_ALGORITHM`  JWT algorithm (default: `HS256`).
- `ACCESS_TOKEN_MINUTES`  access token lifetime in minutes (default: 7 days).
- `REFRESH_TOKEN_DAYS`  refresh token lifetime in days (default: 90).
- `FLASK_DEBUG`  set to `true`/`1` to enable debug mode (development only).
- `PORT`  optional port override for HTTP server (default: 5000).
- `MASTER_ADMIN_PASSWORD`  required in production to allow privileged admin signup.

## CLI options

When running directly with `python server.py`, the following flags are supported:

- `--port PORT`  override the HTTP port (defaults to 5000 or the `PORT` environment variable).
- `--no-scheduler`  do not start the background `TaskScheduler`.
- `--no-worker`  do not start the notification worker thread.

Example:

```bash
python server.py --port 8000 --no-scheduler --no-worker
```

## Project structure

- `server.py`  main entrypoint, creates the Flask app and starts Socket.IO and background scheduler.
- `fin_server/routes`  HTTP route handlers grouped by domain (auth, user, pond, fish, etc.).
- `fin_server/repository`  MongoDB data access layer and helpers.
- `fin_server/dto`  data transfer objects for API payloads.
- `fin_server/security`  JWT authentication utilities.
- `fin_server/notification`  scheduler and notification worker logic.
- `fin_mongo`  seed data and Mongo-related fixtures (e.g. fish reference JSON).
- `templates/API_DOC.html`  HTML documentation for the API.
