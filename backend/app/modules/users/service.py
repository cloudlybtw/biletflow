import uuid
from dataclasses import dataclass

from sqlalchemy import column, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizers.models import OrganizerProfile
from app.modules.users.models import StaffAssignment, StaffRole, User
from app.modules.users.schemas import UpdateMeRequest

# Just the columns permission checks need, until the Event model lands (M2);
# then switch to it.
_events = table("events", column("id"), column("organizer_profile_id"))


@dataclass(frozen=True)
class EventRelation:
    is_owner: bool
    staff_roles: frozenset[StaffRole]


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def is_organizer(session: AsyncSession, user_id: uuid.UUID) -> bool:
    profile_id = await session.scalar(
        select(OrganizerProfile.id).where(OrganizerProfile.user_id == user_id)
    )
    return profile_id is not None


async def update_me(session: AsyncSession, user: User, data: UpdateMeRequest) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    return user


async def get_event_relation(
    session: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
) -> EventRelation | None:
    """How `user_id` relates to the event, or None if the event doesn't exist."""
    owner_user_id = await session.execute(
        select(OrganizerProfile.user_id)
        .select_from(_events)
        .join(OrganizerProfile, OrganizerProfile.id == _events.c.organizer_profile_id)
        .where(_events.c.id == event_id)
    )
    row = owner_user_id.one_or_none()
    if row is None:
        return None
    roles = await session.scalars(
        select(StaffAssignment.role).where(
            StaffAssignment.event_id == event_id,
            StaffAssignment.user_id == user_id,
            StaffAssignment.revoked_at.is_(None),
        )
    )
    return EventRelation(is_owner=row[0] == user_id, staff_roles=frozenset(roles.all()))
