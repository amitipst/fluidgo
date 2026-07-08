"""Email sending for fluidGo. Currently used only for password reset.

Design notes:
- Uses plain smtplib over STARTTLS (M365 = smtp.office365.com:587). No extra deps.
- If SMTP isn't configured yet (no user/password in .env), we DON'T fail — we log
  the reset link to the backend console. This keeps the whole flow testable before
  IT provisions the mailbox: you can grab the link from `docker compose logs backend`.
- Sending runs in a thread via asyncio.to_thread so it never blocks the request loop.
"""
import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

log = logging.getLogger("fluidgo.email")


def _send_sync(to_email: str, subject: str, html_body: str, text_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())


async def send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Returns True if actually sent, False if only logged (SMTP not configured)."""
    if not settings.email_configured:
        log.warning(
            "SMTP not configured — email NOT sent. Would have sent to %s:\n"
            "Subject: %s\n%s", to_email, subject, text_body
        )
        return False
    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body, text_body)
        log.info("Sent '%s' to %s", subject, to_email)
        return True
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_email, e)
        # Log the body so a reset isn't lost if SMTP has a transient failure
        log.error("Undelivered body was:\n%s", text_body)
        return False


async def send_password_reset(to_email: str, name: str, reset_link: str, ttl_minutes: int):
    subject = "Reset your fluidGo password"
    text_body = (
        f"Hi {name},\n\n"
        f"We received a request to reset your fluidGo password.\n"
        f"Click the link below to set a new one. This link expires in {ttl_minutes} minutes "
        f"and can be used only once.\n\n"
        f"{reset_link}\n\n"
        f"If you didn't request this, you can safely ignore this email — your password "
        f"won't change.\n\n"
        f"— fluidGo, WEP Solutions"
    )
    html_body = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:0 auto;color:#1A0B2E">
  <div style="background:linear-gradient(135deg,#F0115E,#92278E);padding:20px 24px;border-radius:12px 12px 0 0">
    <div style="color:#fff;font-size:20px;font-weight:700">fluidGo</div>
    <div style="color:rgba(255,255,255,0.8);font-size:12px">WEP Solutions · Sales Intelligence</div>
  </div>
  <div style="border:1px solid #eee;border-top:none;padding:24px;border-radius:0 0 12px 12px">
    <p>Hi {name},</p>
    <p>We received a request to reset your fluidGo password. Click below to set a new one.</p>
    <p style="text-align:center;margin:28px 0">
      <a href="{reset_link}" style="background:#F0115E;color:#fff;text-decoration:none;
         padding:12px 28px;border-radius:10px;font-weight:700;display:inline-block">
        Reset Password
      </a>
    </p>
    <p style="color:#666;font-size:13px">
      This link expires in <strong>{ttl_minutes} minutes</strong> and can be used only once.
      If you didn't request this, you can safely ignore this email — your password won't change.
    </p>
    <p style="color:#999;font-size:12px;border-top:1px solid #eee;padding-top:12px;margin-top:20px">
      If the button doesn't work, paste this link into your browser:<br>
      <span style="word-break:break-all">{reset_link}</span>
    </p>
  </div>
</div>"""
    return await send_email(to_email, subject, html_body, text_body)
