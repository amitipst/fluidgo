"""Email sending for fluidGo. Used for password reset and (2026-08-04) the
Minutes of Meeting "Send to Customer" feature.

Design notes:
- Uses plain smtplib over STARTTLS (M365 = smtp.office365.com:587). No extra deps.
- If SMTP isn't configured yet (no user/password in .env), we DON'T fail — we log
  the message to the backend console instead. This keeps the whole flow testable
  before IT provisions the mailbox: grab the link/body from `docker compose logs backend`.
- Sending runs in a thread via asyncio.to_thread so it never blocks the request loop.
- to_emails/cc_emails are lists (not a single string) — Cc and multiple
  recipients are both real needs for Send-to-Customer, and doing this once
  properly here means every future caller gets it for free, not just the
  next feature that happens to need it.
"""
import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app.config import settings

log = logging.getLogger("fluidgo.email")


def _send_sync(to_emails: list[str], subject: str, html_body: str, text_body: str,
               cc_emails: list[str] | None = None,
               attachment: tuple[str, bytes, str] | None = None):
    # "mixed" (not "alternative") once there's an attachment — alternative is
    # for html/plain versions of the SAME content, mixed is for content +
    # attachments. Using the wrong one is the standard way this silently
    # produces an email the attachment never actually reaches.
    msg = MIMEMultipart("mixed" if attachment else "alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = ", ".join(to_emails)
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    body = MIMEMultipart("alternative") if attachment else msg
    body.attach(MIMEText(text_body, "plain"))
    body.attach(MIMEText(html_body, "html"))
    if attachment:
        msg.attach(body)
        filename, content, mimetype = attachment
        _, _, subtype = mimetype.partition("/")
        part = MIMEApplication(content, _subtype=subtype or "octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    # The envelope recipient list is separate from the To/Cc HEADERS above —
    # smtplib doesn't read them back out of the message, both need setting.
    envelope_recipients = list(to_emails) + list(cc_emails or [])
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, envelope_recipients, msg.as_string())


async def send_email(to_emails: list[str], subject: str, html_body: str, text_body: str,
                      cc_emails: list[str] | None = None,
                      attachment: tuple[str, bytes, str] | None = None) -> bool:
    """Returns True if actually sent, False if only logged (SMTP not configured).
    attachment, if given, is (filename, content_bytes, mimetype)."""
    if not settings.email_configured:
        log.warning(
            "SMTP not configured — email NOT sent. Would have sent to %s (cc: %s):\n"
            "Subject: %s\n%s", to_emails, cc_emails or [], subject, text_body
        )
        return False
    try:
        await asyncio.to_thread(_send_sync, to_emails, subject, html_body, text_body,
                                 cc_emails, attachment)
        log.info("Sent '%s' to %s (cc: %s)", subject, to_emails, cc_emails or [])
        return True
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_emails, e)
        # Log the body so nothing is lost if SMTP has a transient failure
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
    return await send_email([to_email], subject, html_body, text_body)
