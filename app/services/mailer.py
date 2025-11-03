from typing import Iterable


def send_bulk_email(users: Iterable, subject: str, message: str) -> int:
    """Placeholder mailer service. Replace with real SMTP or provider integration.
    Expects each user to have 'email' attribute.
    Returns number of emails 'sent'.
    """
    # TODO: Implement using smtplib or a transactional provider.
    return sum(1 for u in users if getattr(u, 'email', None))
