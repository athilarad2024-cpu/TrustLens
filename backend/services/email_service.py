"""
services/email_service.py
Email delivery for TrustAI — Gmail SMTP + dev console fallback.

PRODUCTION (Gmail):
  Set SMTP_USERNAME and SMTP_PASSWORD in backend/.env
  Use a Gmail App Password (16 chars), NOT your regular Gmail password.
  https://myaccount.google.com/apppasswords

DEV FALLBACK:
  If SMTP_USERNAME or SMTP_PASSWORD is missing / still placeholder,
  the reset URL is printed clearly to the backend console.
  Never silently discards the email.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("trustai.email")

_PLACEHOLDER = {"your-gmail@gmail.com", "your-16-char-app-password", ""}


def _smtp_ready() -> bool:
    """Return True only when real SMTP credentials are present."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USERNAME", "").strip()
    pwd  = os.getenv("SMTP_PASSWORD", "").strip()
    ready = bool(host) and user not in _PLACEHOLDER and pwd not in _PLACEHOLDER
    print(f"[EMAIL] _smtp_ready check: host='{host}', user='{user}', pwd_len={len(pwd)}, ready={ready}")
    return ready


def send_password_reset_email(to_email: str, reset_url: str, user_name: str) -> None:
    """
    Send a password-reset email to the user.

    Falls back to printing the URL in the backend console if SMTP is not
    configured, rather than silently failing.
    """
    print(f"[EMAIL] send_password_reset_email called: to={to_email}, url={reset_url}")
    if not _smtp_ready():
        print(f"[EMAIL] SMTP NOT READY — falling back to console")
        _print_dev_fallback(to_email, reset_url)
        return

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    # Strip spaces from App Password (e.g. 'rrpm tspr zcnq rqqv' -> 'rrpmtsprzcnqrqqv')
    smtp_pass = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
    from_name = os.getenv("SMTP_FROM_NAME", "TrustAI").strip()
    from_addr = os.getenv("SMTP_FROM_EMAIL", smtp_user).strip()
    use_tls   = os.getenv("SMTP_TLS", "true").lower() != "false"

    subject   = "Reset your TrustAI password"
    from_header = f"{from_name} <{from_addr}>"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="520" cellpadding="0" cellspacing="0" border="0"
             style="background:#1e293b;border:1px solid #334155;border-radius:16px;overflow:hidden;max-width:520px;width:100%;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#4f46e5,#06b6d4);padding:32px;text-align:center;">
          <div style="font-size:28px;font-weight:800;color:#fff;letter-spacing:-0.5px;">
            Trust<span style="color:#c7d2fe;">AI</span>
          </div>
          <div style="color:#e0e7ff;font-size:13px;margin-top:4px;">Multimodal Digital Content Trust System</div>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:36px 40px;">
          <h2 style="color:#f1f5f9;font-size:20px;margin:0 0 12px;">Password Reset Request</h2>
          <p style="color:#94a3b8;line-height:1.7;margin:0 0 28px;">
            Hi <strong style="color:#e2e8f0;">{user_name}</strong>,<br><br>
            We received a request to reset your TrustAI password.
            Click the button below — this link is valid for
            <strong style="color:#e2e8f0;">30 minutes</strong> and can only be used once.
          </p>

          <!-- Button -->
          <div style="text-align:center;margin:32px 0;">
            <a href="{reset_url}"
               style="display:inline-block;background:#4f46e5;color:#fff;
                      padding:15px 36px;border-radius:12px;font-weight:700;
                      text-decoration:none;font-size:15px;letter-spacing:0.2px;">
              Reset My Password
            </a>
          </div>

          <!-- Fallback URL -->
          <p style="color:#64748b;font-size:12px;line-height:1.6;margin:0 0 16px;">
            If the button doesn't work, copy and paste this link into your browser:<br>
            <a href="{reset_url}" style="color:#818cf8;word-break:break-all;">{reset_url}</a>
          </p>

          <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
          <p style="color:#64748b;font-size:12px;line-height:1.6;margin:0;">
            If you didn't request a password reset, you can safely ignore this email.
            Your password will remain unchanged.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#0f172a;padding:20px 40px;text-align:center;">
          <p style="color:#475569;font-size:11px;margin:0;">
            TrustAI &nbsp;·&nbsp; Multimodal Digital Content Trust System
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    plain_body = (
        f"TrustAI — Password Reset\n\n"
        f"Hi {user_name},\n\n"
        f"Reset your password using this link (valid 30 minutes):\n{reset_url}\n\n"
        f"If you didn't request this, ignore this email.\n\n"
        f"— TrustAI"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_header
    msg["To"]      = to_email
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    # Attempt sending via 587 STARTTLS or 465 SSL
    sent = False
    errors = []

    # Strategy 1: Port 587 with STARTTLS
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
            sent = True
            logger.info("Password reset email sent via port 587 to %s", to_email)
    except Exception as exc:
        errors.append(f"Port 587 failed: {exc}")

    # Strategy 2: Port 465 with SSL fallback
    if not sent:
        try:
            with smtplib.SMTP_SSL(smtp_host, 465, timeout=15) as server:
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_addr, [to_email], msg.as_string())
                sent = True
                logger.info("Password reset email sent via port 465 (SSL) to %s", to_email)
        except Exception as exc:
            errors.append(f"Port 465 failed: {exc}")

    if sent:
        print(f"SUCCESS: Password reset email delivered to {to_email}")
    else:
        logger.error("Failed to send reset email: %s", "; ".join(errors))
        _print_dev_fallback(to_email, reset_url)


def _print_dev_fallback(to_email: str, reset_url: str) -> None:
    """Print the reset URL to the backend console (dev fallback)."""
    separator = "=" * 70
    logger.warning(
        "\n%s\n"
        "  [DEV EMAIL] SMTP not configured — printing reset link to console.\n"
        "  Recipient : %s\n"
        "  Reset URL : %s\n"
        "  \n"
        "  To send real emails, edit backend/.env:\n"
        "    SMTP_USERNAME=your-gmail@gmail.com\n"
        "    SMTP_PASSWORD=your-16-char-app-password\n"
        "  Get an App Password at: https://myaccount.google.com/apppasswords\n"
        "%s",
        separator,
        to_email,
        reset_url,
        separator,
    )
