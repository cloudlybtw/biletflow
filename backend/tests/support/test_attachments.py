import io

from PIL import Image

from tests.factories import auth_headers
from tests.support.helpers import opened_case, reply


def screenshot():
    out = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(out, format="PNG")
    return out.getvalue()


async def test_screenshot_attachments_are_private_and_notes_stay_staff_only(
    client, ctx, tmp_path, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    case = await opened_case(client, ctx)
    base = f"/api/v1/support/cases/{case['id']}"
    message = await reply(client, case, ctx.buyer)
    upload = await client.post(
        base + f"/messages/{message.json()['id']}/attachments",
        headers=auth_headers(ctx.buyer),
        files={"file": ("../../bad.html", screenshot(), "text/html")},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    assert attachment["filename"] == "screenshot.png" and attachment["mime_type"] == "image/png"
    assert (
        await client.get(attachment["file_url"], headers=auth_headers(ctx.buyer))
    ).content.startswith(b"\x89PNG")
    assert (
        await client.get(attachment["file_url"], headers=auth_headers(ctx.other))
    ).status_code == 404
    assert (await client.get(attachment["file_url"])).status_code == 401
    note = await reply(client, case, ctx.staff, is_internal_note=True)
    note_upload = await client.post(
        base + f"/messages/{note.json()['id']}/attachments",
        headers=auth_headers(ctx.staff),
        files={"file": ("note.png", screenshot(), "image/png")},
    )
    assert note_upload.status_code == 201
    assert (
        await client.get(note_upload.json()["file_url"], headers=auth_headers(ctx.buyer))
    ).status_code == 404
    assert (await client.get(base + "/attachments", headers=auth_headers(ctx.buyer))).json()[
        "total"
    ] == 1
    assert (await client.get(base + "/attachments", headers=auth_headers(ctx.staff))).json()[
        "total"
    ] == 2
    foreign = await client.post(
        base + f"/messages/{message.json()['id']}/attachments",
        headers=auth_headers(ctx.staff),
        files={"file": ("x.png", screenshot(), "image/png")},
    )
    assert foreign.status_code == 403


async def test_bad_screenshots_and_oversize_uploads_are_rejected(
    client, ctx, tmp_path, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    monkeypatch.setattr(get_settings(), "image_max_bytes", 1000)
    case = await opened_case(client, ctx)
    message = await reply(client, case, ctx.buyer)
    path = f"/api/v1/support/cases/{case['id']}/messages/{message.json()['id']}/attachments"
    bad = await client.post(
        path,
        headers=auth_headers(ctx.buyer),
        files={"file": ("x.svg", b"<script>alert(1)</script>", "image/svg+xml")},
    )
    assert bad.status_code == 422
    large = await client.post(
        path, headers=auth_headers(ctx.buyer), files={"file": ("x.png", b"x" * 1001, "image/png")}
    )
    assert large.status_code == 413
    assert not list(tmp_path.rglob("*.png"))
