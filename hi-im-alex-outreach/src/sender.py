"""Gmail SMTP sender. DISABLED by default — POC only drafts.

To enable: pass --really-send to the CLI and set GMAIL_USER + GMAIL_APP_PASSWORD env vars.
"""
import os
import smtplib
from email.message import EmailMessage


def send_email(to_addr: str, subject: str, body: str) -> None:
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
