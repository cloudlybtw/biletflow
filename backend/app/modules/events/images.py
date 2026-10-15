import asyncio
import io
import uuid
import warnings
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import EventAccess
from app.core.errors import NOT_FOUND, AppError
from app.modules.events.models import EventImage
from app.modules.events.schemas import ImageUpdate
from app.modules.events.service import audit, editable, get_event


def image_path(image: EventImage) -> Path:
    return get_settings().media_root / f"{image.id}.png"


def normalize_image(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or image.width * image.height > 16_000_000
                ):
                    raise ValueError("Only PNG/JPEG/WebP up to 16 megapixels are allowed.")
                image.load()
                normalized = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                out = io.BytesIO()
                normalized.save(out, format="PNG")
                return out.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise AppError(
            "INVALID_IMAGE", "Upload a valid PNG, JPEG or WebP image up to 16 megapixels.", 422
        ) from exc


async def upload(
    session: AsyncSession,
    access: EventAccess,
    file: UploadFile,
    is_cover: bool,
    alt_text: str | None,
) -> EventImage:
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    data = await file.read(get_settings().image_max_bytes + 1)
    await file.close()
    if len(data) > get_settings().image_max_bytes:
        raise AppError("IMAGE_TOO_LARGE", "Image exceeds the upload size limit.", 413)
    data = await asyncio.to_thread(normalize_image, data)
    if is_cover:
        await session.execute(
            update(EventImage)
            .where(EventImage.event_id == event.id, EventImage.is_cover)
            .values(is_cover=False)
        )
    image = EventImage(
        id=uuid.uuid4(), event_id=event.id, is_cover=is_cover, alt_text=alt_text, url=""
    )
    image.url = f"/api/v1/events/{event.id}/images/{image.id}/file"
    path = image_path(image)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(path.write_bytes, data)
        session.add(image)
        await session.flush()
        await audit(session, access, "event_image.uploaded", image)
        await session.commit()
    except Exception:
        await session.rollback()
        path.unlink(missing_ok=True)
        raise
    return image


async def get_image(session: AsyncSession, event_id: uuid.UUID, image_id: uuid.UUID) -> EventImage:
    image = await session.scalar(
        select(EventImage).where(EventImage.id == image_id, EventImage.event_id == event_id)
    )
    if image is None:
        raise AppError(NOT_FOUND, "Image not found.", 404)
    return image


async def edit(
    session: AsyncSession, access: EventAccess, image_id: uuid.UUID, data: ImageUpdate
) -> EventImage:
    editable(await get_event(session, access.event_id, lock=True))
    image = await get_image(session, access.event_id, image_id)
    if data.is_cover:
        await session.execute(
            update(EventImage)
            .where(EventImage.event_id == access.event_id, EventImage.is_cover)
            .values(is_cover=False)
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(image, field, value)
    await audit(session, access, "event_image.updated", image)
    await session.commit()
    return image


async def delete(session: AsyncSession, access: EventAccess, image_id: uuid.UUID) -> None:
    editable(await get_event(session, access.event_id, lock=True))
    image = await get_image(session, access.event_id, image_id)
    path = image_path(image)
    await audit(session, access, "event_image.deleted", image)
    await session.delete(image)
    await session.commit()
    path.unlink(missing_ok=True)
