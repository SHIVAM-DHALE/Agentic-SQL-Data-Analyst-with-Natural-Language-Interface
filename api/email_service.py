"""Password-reset email delivery with an explicitly development-only console mode."""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}


def build_password_reset_link(reset_token: str) -> str:
    """Build the frontend link without treating the token as trusted URL text."""

    base_url = os.getenv("PASSWORD_RESET_BASE_URL", "http://localhost:8501").strip()
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}reset_token={quote(reset_token, safe='')}"


def _masked_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain}"


def send_password_reset_email(recipient: str, reset_token: str) -> None:
    """Deliver a reset link by SMTP or emit it in development console mode.

    ``EMAIL_DELIVERY_MODE=console`` is rejected in production.  It provides a
    simple local workflow without adding a route that exposes reset tokens.
    """

    production = _is_production()
    default_mode = "smtp" if production else "console"
    mode = os.getenv("EMAIL_DELIVERY_MODE", default_mode).strip().lower()
    reset_link = build_password_reset_link(reset_token)

    if mode == "console":
        if production:
            raise RuntimeError("Console password-reset delivery is disabled in production")
        logger.warning(
            "Development password reset link for %s: %s",
            _masked_email(recipient),
            reset_link,
        )
        return

    if mode == "disabled":
        if production:
            raise RuntimeError("Password-reset email delivery cannot be disabled in production")
        logger.info("Development password-reset email delivery is disabled")
        return

    if mode != "smtp":
        raise RuntimeError("EMAIL_DELIVERY_MODE must be smtp, console, or disabled")

    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM_EMAIL", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for SMTP delivery")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = _as_bool("SMTP_USE_SSL", False)
    use_starttls = _as_bool("SMTP_USE_STARTTLS", not use_ssl)
    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))

    message = EmailMessage()
    message["Subject"] = "Reset your Agentic SQL password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your Agentic SQL account.\n\n"
        f"Open this link to choose a new password:\n{reset_link}\n\n"
        "This link expires soon and can be used only once. If you did not "
        "request it, you can safely ignore this email."
    )

    context = ssl.create_default_context()
    if use_ssl:
        smtp_client: smtplib.SMTP = smtplib.SMTP_SSL(
            host, port, timeout=timeout, context=context
        )
    else:
        smtp_client = smtplib.SMTP(host, port, timeout=timeout)

    with smtp_client as client:
        client.ehlo()
        if use_starttls and not use_ssl:
            client.starttls(context=context)
            client.ehlo()
        if username:
            client.login(username, password)
        client.send_message(message)
