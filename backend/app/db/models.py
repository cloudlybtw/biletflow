"""Import every model module so all mappers are registered on Base.metadata.

Import this (not individual model modules) from the app, tests and scripts.
Add each new domain's models module here as it lands.
"""

from app.db import settings as settings_models
from app.modules.activation import models as activation_models
from app.modules.auth import models as auth_models
from app.modules.campaigns import models as campaigns_models
from app.modules.checkin import models as checkin_models
from app.modules.events import models as events_models
from app.modules.history import models as history_models
from app.modules.notifications import models as notifications_models
from app.modules.orders import models as orders_models
from app.modules.organizers import models as organizers_models
from app.modules.payments import models as payments_models
from app.modules.refunds import models as refunds_models
from app.modules.support import models as support_models
from app.modules.ticketing import holds as holds_models
from app.modules.ticketing import models as ticketing_models
from app.modules.tickets import models as tickets_models
from app.modules.users import models as users_models
from app.modules.venues import models as venues_models

__all__ = [
    "activation_models",
    "auth_models",
    "history_models",
    "notifications_models",
    "organizers_models",
    "users_models",
    "events_models",
    "venues_models",
    "ticketing_models",
    "campaigns_models",
    "checkin_models",
    "settings_models",
    "orders_models",
    "payments_models",
    "refunds_models",
    "support_models",
    "tickets_models",
    "holds_models",
]
