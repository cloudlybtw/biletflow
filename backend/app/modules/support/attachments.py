"""Private, bounded screenshot attachments; never expose the media directory."""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_support_case
from app.core.errors import AppError
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.events.images import normalize_image
from app.modules.support import service
from app.modules.support.models import SupportAttachment, SupportMessage
from app.modules.support.service import CaseAccess

router = APIRouter(tags=["support attachments"])


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    message_id: uuid.UUID
    file_url: str
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime


async def visible_message(session, access, message_id):
    message = await session.scalar(
        select(SupportMessage).where(
            SupportMessage.id == message_id, SupportMessage.case_id == access.case.id
        )
    )
    if message is None or (message.is_internal_note and not access.can_read_internal):
        raise AppError("NOT_FOUND", "Message not found.", 404)
    return message


def storage_path(attachment_id):
    return get_settings().media_root / "support-attachments" / f"{attachment_id}.png"


@router.post(
    "/support/cases/{case_id}/messages/{message_id}/attachments",
    response_model=AttachmentOut,
    status_code=201,
)
async def upload(
    message_id: uuid.UUID,
    file: UploadFile,
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    access = await service.access_case(session, access.user, access.case.id, lock=True)
    message = await visible_message(session, access, message_id)
    if message.sender_user_id != access.user.id:
        raise AppError("FORBIDDEN", "Attach screenshots only to your own messages.", 403)
    count = await session.scalar(
        select(func.count())
        .select_from(SupportAttachment)
        .where(SupportAttachment.message_id == message.id)
    )
    if count >= 5:
        raise AppError("ATTACHMENT_LIMIT", "At most five screenshots per message.", 409)
    data = await file.read(get_settings().image_max_bytes + 1)
    await file.close()
    if len(data) > get_settings().image_max_bytes:
        raise AppError("ATTACHMENT_TOO_LARGE", "Screenshot exceeds the upload limit.", 413)
    data = await asyncio.to_thread(normalize_image, data)
    if len(data) > get_settings().image_max_bytes:
        raise AppError(
            "ATTACHMENT_TOO_LARGE", "Normalized screenshot exceeds the upload limit.", 413
        )
    attachment_id = uuid.uuid4()
    attachment = SupportAttachment(
        id=attachment_id,
        message_id=message.id,
        file_url=f"/api/v1/support/cases/{access.case.id}/attachments/{attachment_id}",
        filename="screenshot.png",
        mime_type="image/png",
        size_bytes=len(data),
    )
    path = storage_path(attachment_id)
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(path.write_bytes, data)
        session.add(attachment)
        await session.flush()
        await service.audit(
            session,
            access,
            "support.attachment_added",
            {"attachment_id": str(attachment.id), "message_id": str(message.id)},
        )
        result = AttachmentOut.model_validate(attachment)
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(path.unlink, missing_ok=True)
        raise
    return result


@router.get("/support/cases/{case_id}/attachments", response_model=Page[AttachmentOut])
async def attachments(
    access: CaseAccess = Depends(require_support_case),
    page: Pagination = Depends(pagination),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(SupportAttachment)
        .join(SupportMessage, SupportMessage.id == SupportAttachment.message_id)
        .where(SupportMessage.case_id == access.case.id)
    )
    if not access.can_read_internal:
        statement = statement.where(~SupportMessage.is_internal_note)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    items = (
        await session.scalars(
            statement.order_by(SupportAttachment.created_at, SupportAttachment.id)
            .offset(page.offset)
            .limit(page.limit)
        )
    ).all()
    return Page(items=items, total=total)


@router.get("/support/cases/{case_id}/attachments/{attachment_id}", response_class=FileResponse)
async def download(
    attachment_id: uuid.UUID,
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    attachment = await session.get(SupportAttachment, attachment_id)
    if attachment is None:
        raise AppError("NOT_FOUND", "Attachment not found.", 404)
    await visible_message(session, access, attachment.message_id)
    path = storage_path(attachment.id)
    if not await asyncio.to_thread(path.is_file):
        raise AppError("NOT_FOUND", "Attachment file not found.", 404)
    return FileResponse(
        path,
        media_type="image/png",
        filename=attachment.filename,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
