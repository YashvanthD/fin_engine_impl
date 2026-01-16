from .routes.auth import auth_bp
from .routes.user import user_bp
from .routes.task import task_bp
from .routes.company import company_bp
from .routes.pond import pond_bp
from .routes.fish import fish_bp
from .routes.pond_event import pond_event_bp
from .routes.public import public_bp
from .routes.feeding import feeding_bp
from .routes.sampling import sampling_bp
from .routes.expenses import expenses_bp
from .routes.dashboard import dashboard_bp
from .routes.role import role_bp
from .routes.permission import permission_bp

# Application factory is defined in server.py for now; we re-export the
# blueprints here so that other code (tests, alternative runners) can
# build an app without importing server.py and triggering side-effects.

__all__ = [
    "auth_bp",
    "user_bp",
    "task_bp",
    "company_bp",
    "pond_bp",
    "fish_bp",
    "pond_event_bp",
    "public_bp",
    "feeding_bp",
    "sampling_bp",
    "expenses_bp",
    "dashboard_bp",
    "role_bp",
    "permission_bp",
]
