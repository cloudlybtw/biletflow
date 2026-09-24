import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.history.models import AuditLog


async def record(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    actor_role: str | None,
    action_type: str,
    entity_type: str,
    entity_id: uuid.UUID | str,
    summary: str,
    event_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append an audit row in the caller's transaction, so it commits with the change."""
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            event_id=event_id,
            summary=summary,
            metadata_=metadata or {},
        )
    )
    await session.flush()
