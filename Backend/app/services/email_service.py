import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered via SMTP."""
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
        """Checks if SMTP credentials are configured in the environment."""
        return bool(self.user and self.password)

    def send_otp_email(self, recipient_email: str, otp_code: str, recipient_name: str = "User") -> None:
        """
        Sends an email containing the 6-digit OTP code to the recipient.
        Uses Gmail SMTP with STARTTLS.
        """
        if not self.is_configured():
            # In development mode without credentials, print the code to the terminal for easy testing
            print(
                f"\n"
                f"======================================================\n"
                f" [DEV MODE] SMTP CREDENTIALS NOT CONFIGURED IN .env\n"
                f" Recipient: {recipient_email}\n"
                f" Verification OTP Code: >>> {otp_code} <<<\n"
                f" (Enter this code in your browser to verify your account)\n"
                f"======================================================\n"
            )
            return

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

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
                server.sendmail(self.from_email, [recipient_email], msg.as_string())
        except smtplib.SMTPException as e:
            # Raise a custom exception without exposing SMTP credentials in the error trace
            raise EmailDeliveryError(f"Failed to send email via SMTP: {type(e).__name__}")
        except Exception as e:
            raise EmailDeliveryError(f"Unexpected email delivery failure: {type(e).__name__}")


email_service = EmailService()

