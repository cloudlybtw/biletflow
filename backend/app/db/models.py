"""Import every model module so all mappers are registered on Base.metadata.

Import this (not individual model modules) from the app, tests and scripts.
Add each new domain's models module here as it lands.
"""

from app.modules.auth import models as auth_models
from app.modules.history import models as history_models
from app.modules.notifications import models as notifications_models
from app.modules.organizers import models as organizers_models
from app.modules.users import models as users_models

__all__ = [
    "auth_models",
    "history_models",
    "notifications_models",
    "organizers_models",
    "users_models",
]
