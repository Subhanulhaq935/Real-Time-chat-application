import smtplib
import ssl
import json
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered via SMTP or Email API."""
    pass


class EmailService:
    @property
    def host(self) -> str:
        return settings.SMTP_HOST

    @property
    def port(self) -> int:
        return settings.SMTP_PORT

    @property
    def user(self) -> str:
        return settings.SMTP_USER

    @property
    def password(self) -> str:
        return settings.SMTP_PASSWORD

    @property
    def from_email(self) -> str:
        return settings.EMAILS_FROM_EMAIL or settings.SMTP_USER

    @property
    def from_name(self) -> str:
        return settings.EMAILS_FROM_NAME

    def is_configured(self) -> bool:
        """Checks if SMTP credentials, Resend API, or Brevo API are configured."""
        has_smtp = bool(self.user and self.password)
        has_resend = bool(getattr(settings, "RESEND_API_KEY", "").strip())
        has_brevo = bool(getattr(settings, "BREVO_API_KEY", "").strip())
        return has_smtp or has_resend or has_brevo

    def _send_via_resend(self, recipient_email: str, subject: str, html_content: str, text_content: str) -> bool:
        api_key = getattr(settings, "RESEND_API_KEY", "").strip()
        if not api_key:
            return False

        try:
            from_address = f"{self.from_name} <onboarding@resend.dev>"
            if self.from_email and not self.from_email.endswith("@gmail.com"):
                from_address = f"{self.from_name} <{self.from_email}>"

            payload = json.dumps({
                "from": from_address,
                "to": [recipient_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "PulseChat/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise EmailDeliveryError(f"Resend API error ({e.code}): {err_body}")
        except Exception as e:
            raise EmailDeliveryError(f"Resend delivery failed: {str(e)}")

    def _send_via_brevo(self, recipient_email: str, subject: str, html_content: str, text_content: str) -> bool:
        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            return False

        try:
            from_email = self.from_email if self.from_email else self.user
            payload = json.dumps({
                "sender": {"name": self.from_name, "email": from_email},
                "to": [{"email": recipient_email}],
                "subject": subject,
                "htmlContent": html_content,
                "textContent": text_content,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=payload,
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "PulseChat/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise EmailDeliveryError(f"Brevo API error ({e.code}): {err_body}")
        except Exception as e:
            raise EmailDeliveryError(f"Brevo delivery failed: {str(e)}")

    def _send_via_smtp(self, recipient_email: str, msg: MIMEMultipart) -> None:
        clean_user = self.user.strip()
        clean_password = self.password.replace(" ", "").strip()
        clean_host = self.host.strip()

        # Try Port 465 (SSL) and Port 587 (STARTTLS) with 3s timeout to fail fast if firewall drops packets
        ports_to_try = [465, 587] if self.port == 465 else [587, 465]
        attempt_errors = []

        for p in ports_to_try:
            try:
                if p == 465:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL(clean_host, 465, timeout=3, context=ctx) as server:
                        server.login(clean_user, clean_password)
                        server.sendmail(self.from_email, [recipient_email], msg.as_string())
                        return
                else:
                    with smtplib.SMTP(clean_host, 587, timeout=3) as server:
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(clean_user, clean_password)
                        server.sendmail(self.from_email, [recipient_email], msg.as_string())
                        return
            except smtplib.SMTPAuthenticationError:
                raise EmailDeliveryError("Gmail SMTP Authentication failed. Please verify your Gmail address and 16-character App Password.")
            except Exception as e:
                attempt_errors.append(f"Port {p}: {type(e).__name__}")

        raise EmailDeliveryError(
            "Render hosting blocks direct SMTP ports (587 & 465). "
            "To send emails reliably from Render, please add a free RESEND_API_KEY in Render Environment Variables."
        )

    def send_otp_email(self, recipient_email: str, otp_code: str, recipient_name: str = "User") -> None:
        """
        Sends an email containing the 6-digit OTP code to the recipient.
        Tries Resend HTTPS API first if configured, then Gmail SMTP (ports 587 & 465).
        """
        subject = f"Your Verification Code: {otp_code} - {self.from_name}"

        # Plain text fallback
        text_content = f"""Hello {recipient_name},

Thank you for signing up for {self.from_name}!

Your 6-digit verification code is: {otp_code}

This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.
If you did not request this code, please ignore this email.

Best regards,
The {self.from_name} Team
"""

        # HTML formatted template
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f7; margin: 0; padding: 20px; }}
    .card {{ background: #ffffff; max-width: 480px; margin: 0 auto; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ font-size: 20px; font-weight: bold; color: #1e1b4b; margin-bottom: 16px; text-align: center; }}
    .text {{ font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 24px; text-align: center; }}
    .otp-box {{ background-color: #eef2ff; border: 2px dashed #6366f1; border-radius: 8px; padding: 16px; text-align: center; margin: 24px 0; }}
    .otp-code {{ font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #4338ca; }}
    .footer {{ font-size: 12px; color: #94a3b8; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">Verify Your Email Address</div>
    <div class="text">Hello <strong>{recipient_name}</strong>,<br>Use the 6-digit code below to complete your registration for {self.from_name}.</div>
    <div class="otp-box">
      <div class="otp-code">{otp_code}</div>
    </div>
    <div class="text">This code will expire in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>. For your security, never share this code with anyone.</div>
    <div class="footer">If you did not create an account, you can safely ignore this message.</div>
  </div>
</body>
</html>
"""

        # 1. Try Resend API if API key is provided
        if getattr(settings, "RESEND_API_KEY", "").strip():
            if self._send_via_resend(recipient_email, subject, html_content, text_content):
                return

        # 2. Try Brevo API if API key is provided
        if getattr(settings, "BREVO_API_KEY", "").strip():
            if self._send_via_brevo(recipient_email, subject, html_content, text_content):
                return

        # 3. Check SMTP credentials
        if not (self.user and self.password):
            raise EmailDeliveryError("Email delivery service is not configured. Please check SMTP settings or add RESEND_API_KEY in server configuration.")

        # 3. Deliver via SMTP (with 465 SSL & 587 STARTTLS auto-fallback)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        self._send_via_smtp(recipient_email, msg)


email_service = EmailService()

