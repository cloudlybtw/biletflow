"""English fallback for all supported locales; never render arbitrary payload fields."""

from app.core.config import get_settings
from app.modules.notifications.models import NotificationType

SUBJECTS = {
    NotificationType.ACCOUNT_VERIFICATION: "Verify your BiletFlow email",
    NotificationType.PASSWORD_RESET: "Reset your BiletFlow password",
    NotificationType.ORDER_CONFIRMATION: "Your BiletFlow registration is confirmed",
    NotificationType.PAYMENT_FAILED: "Your simulated payment failed",
    NotificationType.TICKET_DELIVERY: "Your BiletFlow tickets are ready",
    NotificationType.EVENT_UPDATE: "Your BiletFlow registration or event was updated",
    NotificationType.EVENT_CANCELLED: "Your BiletFlow event was cancelled",
    NotificationType.REFUND_COMPLETED: "Your simulated refund is complete",
    NotificationType.PAYOUT_STATUS: "Your simulated payout status changed",
    NotificationType.SUPPORT_NEW_MESSAGE: "New support message",
    NotificationType.SUPPORT_ASSIGNED: "Support case assignment changed",
    NotificationType.SUPPORT_STATUS_CHANGED: "Support case status changed",
}


def render(
    kind: NotificationType, payload: dict, locale: str = "en", *, private=False
) -> tuple[str, str]:
    # kk/ru use the permitted English MVP fallback. SMTP declares Content-Language: en.
    subject = SUBJECTS[kind]
    lines = [subject + "."]
    if kind in (NotificationType.ACCOUNT_VERIFICATION, NotificationType.PASSWORD_RESET):
        key = "verify_url" if kind == NotificationType.ACCOUNT_VERIFICATION else "reset_url"
        lines.append(
            payload[key] if private else "Open the email sent to your account to continue."
        )
    elif kind.value.startswith("support_"):
        lines.append(f"Case: {payload.get('case_number', 'BiletFlow support')}")
        if kind == NotificationType.SUPPORT_STATUS_CHANGED:
            lines.append(f"Status: {payload.get('status', 'updated')}")
        lines.append("Sign in to BiletFlow to view the case.")
    else:
        if payload.get("event_title"):
            lines.append(f"Event: {payload['event_title']}")
        if payload.get("order_number"):
            lines.append(f"Order: {payload['order_number']}")
        if payload.get("status"):
            lines.append(f"Status: {payload['status']}")
        if kind == NotificationType.REFUND_COMPLETED:
            lines.append(f"Refund: {payload.get('amount', 0)} KZT (simulated).")
        elif kind == NotificationType.ORDER_CONFIRMATION:
            lines.append(f"Total: {payload.get('total_amount', 0)} KZT.")
        if kind in (
            NotificationType.ORDER_CONFIRMATION,
            NotificationType.PAYMENT_FAILED,
            NotificationType.PAYOUT_STATUS,
            NotificationType.REFUND_COMPLETED,
        ):
            lines.append("Academic demo only. No real money moves.")
        if kind == NotificationType.TICKET_DELIVERY:
            lines.append(
                "Printable tickets are attached to this email. Sign in to your account for current ticket status and PDF downloads."
                if private
                else "Sign in to your account to view your tickets and download printable PDFs."
            )
        lines.append(f"Your account: {get_settings().web_base_url}")
    return subject, "\n\n".join(str(line) for line in lines)
