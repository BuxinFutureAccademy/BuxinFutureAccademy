from typing import Iterable
import smtplib
from email.message import EmailMessage
from flask import current_app


def send_bulk_email(users: Iterable, subject: str, message: str) -> int:
    """Send plain-text emails to a list of user-like objects with an email attribute.
    Returns the number of successfully sent emails. Fails gracefully and returns 0 on errors.
    """
    smtp_host = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('MAIL_PORT', 587))
    use_tls = str(current_app.config.get('MAIL_USE_TLS', 'true')).lower() == 'true'
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER') or username

    if not username or not password or not default_sender:
        return 0

    sent_count = 0
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        if use_tls:
            server.starttls()
        server.login(username, password)

        for u in users:
            recipient = getattr(u, 'email', None)
            if not recipient:
                continue
            try:
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From'] = default_sender
                msg['To'] = recipient
                msg.set_content(message)
                server.send_message(msg)
                sent_count += 1
            except Exception:
                continue
        try:
            server.quit()
        except Exception:
            pass
    except Exception:
        return 0
    return sent_count
