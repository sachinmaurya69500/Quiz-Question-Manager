import os
import smtplib
import secrets
from email.mime.text import MIMEText

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return generate_password_hash(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    return check_password_hash(otp_hash, otp)


def send_otp_email(recipient_email: str, otp: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = smtp_username
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    if not smtp_host or not smtp_username or not smtp_password:
        raise RuntimeError("SMTP settings are not fully configured.")

    message = MIMEText(
        f"Your Quiz Question Manager verification code is {otp}. It expires soon.",
        "plain",
        "utf-8",
    )
    message["Subject"] = "Your Quiz Question Manager OTP"
    message["From"] = smtp_from_email
    message["To"] = recipient_email

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if smtp_use_tls:
            server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_from_email, [recipient_email], message.as_string())
