"""
services/email_service.py
Email delivery for TrustAI.

Production: uses SMTP credentials from environment variables.
Development fallback: when SMTP_HOST is not set, prints the reset URL to the
backend console only (clearly marked [DEV EMAIL]). Never silently discards.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("trustai.email")


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip())


def send_password_reset_email(to_email: str, reset_url: str, user_name: str) -> None:
    """
    Send a password-reset email.

    If SMTP is not configured (SMTP_HOST is empty), logs the reset URL to the
    server console as a development fallback — never pretends the email was sent.
    """
    if not _smtp_configured():
        # ── DEV FALLBACK ─────────────────────────────────────────────────────
        logger.warning(
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "[DEV EMAIL] Password reset requested for: %s\n"
            "[DEV EMAIL] Open this URL in the browser to reset the password:\n"
            "[DEV EMAIL] %s\n"
            "[DEV EMAIL] (Configure SMTP_HOST in backend/.env to send real emails)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            to_email,
            reset_url,
        )
        return

    # ── Production SMTP ───────────────────────────────────────────────────────
    smtp_host: str = os.environ["SMTP_HOST"]
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USERNAME", "")
    smtp_pass: str = os.getenv("SMTP_PASSWORD", "")
    from_email: str = os.getenv("SMTP_FROM_EMAIL", smtp_user)
    use_tls: bool = os.getenv("SMTP_TLS", "true").lower() != "false"

    subject = "Reset your TrustAI password"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Inter, system-ui, sans-serif; background:#0f172a; color:#e2e8f0; padding:32px;">
      <div style="max-width:520px; margin:0 auto; background:#1e293b;
                  border:1px solid #334155; border-radius:16px; padding:40px;">
        <div style="text-align:center; margin-bottom:32px;">
          <span style="font-size:28px; font-weight:800; color:#fff;">
            Trust<span style="color:#818cf8;">AI</span>
          </span>
        </div>
        <h2 style="color:#f1f5f9; font-size:20px; margin-bottom:8px;">
          Password reset request
        </h2>
        <p style="color:#94a3b8; line-height:1.6;">
          Hi {user_name}, we received a request to reset your TrustAI password.
          Click the button below — it is valid for <strong style="color:#e2e8f0;">30 minutes</strong>.
        </p>
        <div style="text-align:center; margin:32px 0;">
          <a href="{reset_url}"
             style="display:inline-block; background:#4f46e5; color:#fff;
                    padding:14px 32px; border-radius:12px; font-weight:600;
                    text-decoration:none; font-size:15px;">
            Reset my password
          </a>
        </div>
        <p style="color:#64748b; font-size:13px; line-height:1.6;">
          If you did not request this, you can safely ignore this email.<br>
          Your password will not change.
        </p>
        <hr style="border-color:#334155; margin:24px 0;">
        <p style="color:#475569; font-size:12px; text-align:center;">
          TrustAI — Multimodal Digital Content Trust System
        </p>
      </div>
    </body>
    </html>
    """
    text_body = (
        f"TrustAI — Password Reset\n\n"
        f"Hi {user_name},\n\n"
        f"Click the link below to reset your password (valid 30 minutes):\n{reset_url}\n\n"
        f"If you did not request this, ignore this email."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, to_email, msg.as_string())

        logger.info("Password reset email sent to: %s", to_email)
    except Exception as exc:
        logger.error("Failed to send reset email to %s: %s", to_email, exc)
        raise
