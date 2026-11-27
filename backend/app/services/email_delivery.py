from __future__ import annotations

from email.message import EmailMessage
import smtplib
import ssl
from urllib.parse import quote

from app.core.config import Settings


class EmailDeliveryNotConfigured(RuntimeError):
    pass


def validate_email_delivery_config(settings: Settings) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryNotConfigured
    if bool(settings.smtp_username) != bool(settings.smtp_password.get_secret_value()):
        raise EmailDeliveryNotConfigured
    if not settings.smtp_use_ssl and not settings.smtp_starttls:
        raise EmailDeliveryNotConfigured
    if settings.smtp_use_ssl and settings.smtp_starttls:
        raise EmailDeliveryNotConfigured


def send_email_change_verification(settings: Settings, recipient: str, token: str) -> None:
    """Send a single-use verification link without logging or returning its token."""
    validate_email_delivery_config(settings)

    link = (
        f"{settings.email_verification_frontend_url.rstrip('/')}/verify-email-change"
        f"#token={quote(token, safe='')}"
    )
    message = EmailMessage()
    message["Subject"] = "Verify your CoronAI email address"
    message["From"] = str(settings.smtp_from_email)
    message["To"] = recipient
    message.set_content(
        "A request was made to change the email address on your CoronAI account.\n\n"
        f"Open this one-time link within {settings.email_verification_ttl_minutes} minutes to confirm:\n{link}\n\n"
        "If you did not request this change, you can ignore this message. Your current email remains unchanged."
    )

    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context) as smtp:
            _authenticate_and_send(smtp, settings, message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            _authenticate_and_send(smtp, settings, message)


def _authenticate_and_send(smtp: smtplib.SMTP, settings: Settings, message: EmailMessage) -> None:
    if settings.smtp_username:
        smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
    smtp.send_message(message)
