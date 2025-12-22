from .routes.auth import auth_bp, auth_api_bp
from .routes.user import user_bp, user_api_bp
from .routes.task import task_bp, task_api_bp
from .routes.company import company_bp
from .routes.pond import pond_bp, pond_api_bp
from .routes.fish import fish_bp
from .routes.pond_event import pond_event_bp
from .routes.public import public_bp
from .routes.feeding import feeding_bp, feeding_api_bp
from .routes.sampling import sampling_bp, sampling_api_bp

# Application factory is defined in server.py for now; we re-export the
# blueprints here so that other code (tests, alternative runners) can
# build an app without importing server.py and triggering side-effects.

__all__ = [
    "auth_bp", "auth_api_bp",
    "user_bp", "user_api_bp",
    "task_bp", "task_api_bp",
    "company_bp",
    "pond_bp", "pond_api_bp",
    "fish_bp",
    "pond_event_bp",
    "public_bp",
    "feeding_bp", "feeding_api_bp",
    "sampling_bp", "sampling_api_bp",
]

