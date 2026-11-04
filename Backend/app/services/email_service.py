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
        """Checks if SMTP credentials, Resend API, Brevo API, or Relay are configured."""
        has_smtp = bool(self.user and self.password)
        has_resend = bool(getattr(settings, "RESEND_API_KEY", "").strip())
        has_brevo = bool(getattr(settings, "BREVO_API_KEY", "").strip())
        has_relay = bool(getattr(settings, "EMAIL_RELAY_URL", "").strip())
        return has_smtp or has_resend or has_brevo or has_relay

    def _send_via_relay(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        client_origin: str = None,
    ) -> bool:
        """
        Sends email via HTTPS Email Relay (Port 443).
        This bypasses Render hosting's outbound firewall blocks on direct SMTP ports (587 & 465).
        """
        urls_to_try = []

        # If client called from browser, try client's origin relay endpoint first
        if client_origin and isinstance(client_origin, str) and client_origin.startswith("http"):
            relay_url = f"{client_origin.rstrip('/')}/api/send-email"
            if relay_url not in urls_to_try:
                urls_to_try.append(relay_url)

        # Try configured relay URL
        configured_relay = getattr(settings, "EMAIL_RELAY_URL", "").strip()
        if configured_relay and configured_relay not in urls_to_try:
            urls_to_try.append(configured_relay)

        # Default known production Vercel deployment URLs
        default_relays = [
            "https://real-time-chat-application-subhanulhaq935-gmailcoms-projects.vercel.app/api/send-email",
            "https://chat-one-to-one.vercel.app/api/send-email",
        ]
        for d in default_relays:
            if d not in urls_to_try:
                urls_to_try.append(d)

        secret = getattr(settings, "EMAIL_RELAY_SECRET", "pulsechat-secret-relay-key-2026")
        payload = json.dumps({
            "to": recipient_email,
            "subject": subject,
            "html": html_content,
            "text": text_content,
            "secret": secret,
        }).encode("utf-8")

        for url in urls_to_try:
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-relay-secret": secret,
                        "User-Agent": "PulseChat-Backend/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if resp.status in (200, 201):
                        return True
            except Exception:
                continue

        return False

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
            "Direct SMTP connection timed out. Outbound SMTP ports appear firewalled on hosting environment."
        )

    def send_otp_email(
        self,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "User",
        client_origin: str = None,
    ) -> None:
        """
        Sends an email containing the 6-digit OTP code to the recipient.
        Tries HTTPS Email Relay first (works seamlessly on Render hosting via Port 443),
        then Resend/Brevo APIs if configured, and finally direct Gmail SMTP.
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

        # 1. Try HTTPS Email Relay first (Bypasses Render firewall using Port 443)
        if self._send_via_relay(recipient_email, subject, html_content, text_content, client_origin):
            return

        # 2. Try Resend API if API key is provided
        if getattr(settings, "RESEND_API_KEY", "").strip():
            if self._send_via_resend(recipient_email, subject, html_content, text_content):
                return

        # 3. Try Brevo API if API key is provided
        if getattr(settings, "BREVO_API_KEY", "").strip():
            if self._send_via_brevo(recipient_email, subject, html_content, text_content):
                return

        # 4. Check SMTP credentials
        if not (self.user and self.password):
            raise EmailDeliveryError("Email delivery service is not configured. Please check SMTP settings or add RESEND_API_KEY in server configuration.")

        # 5. Deliver via direct SMTP (with 465 SSL & 587 STARTTLS auto-fallback)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        self._send_via_smtp(recipient_email, msg)


email_service = EmailService()
