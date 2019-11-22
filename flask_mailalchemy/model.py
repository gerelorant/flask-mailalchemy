import datetime as dt
from smtplib import SMTPDataError, SMTPSenderRefused, SMTPRecipientsRefused

from flask import current_app
from flask_mail import Message
import sqlalchemy as sa
from werkzeug.local import LocalProxy


db = LocalProxy(lambda: current_app.extensions.get("sqlalchemy").db)
config = LocalProxy(lambda: current_app.config)
mail = LocalProxy(lambda: current_app.extensions.get("mail"))


class MailNotSetError(Exception):
    pass


class MailLimitError(Exception):
    pass


class EmailMixin:
    """Declerative mixin class for e-mail table."""
    sender_address = sa.Column(sa.String(255), nullable=False, index=True)
    sender_name = sa.Column(sa.String(80))
    subject = sa.Column(sa.String(80), nullable=False, index=True)
    recipient = sa.Column(sa.String(255), nullable=False, index=True)
    message_txt = sa.Column(sa.Text)
    message_html = sa.Column(sa.Text)

    scheduled_at = sa.Column(
        sa.DateTime,
        default=dt.datetime.utcnow,
        index=True
    )
    sent_at = sa.Column(
        sa.DateTime,
        default=dt.datetime.utcnow,
        index=True
    )
    error = sa.Column(sa.Text)

    @property
    def message(self) -> Message:
        sender = self.sender_address \
            if self.sender_name is None \
            else (self.sender_name, self.sender_address)
        return Message(
            self.subject,
            [self.recipient],
            self.message_txt,
            self.message_html,
            sender
        )

    @classmethod
    def from_message(cls, msg: Message) -> tuple:
        messages = []

        for recipient in msg.recipients:
            email = cls()
            email.recipient = recipient
            if isinstance(msg.sender, str):
                email.sender_address = msg.sender
            else:
                email.sender_name, email.sender_address = msg.sender
            email.subject = msg.subject
            email.message_html = msg.html
            email.message_txt = msg.body
            messages.append(email)

        return tuple(messages)

    @classmethod
    def check_limit(cls):
        per_minute = config.get("MAIL_PER_MINUTE", None)
        per_hour = config.get("MAIL_PER_HOUR", None)
        per_day = config.get("MAIL_PER_DAY", None)

        now = dt.datetime.utcnow()

        in_minute = db.session.query(sa.func.count(cls))\
            .filter(cls.sent_at > now - dt.timedelta(minutes=1))\
            .first()\
            .scalar()
        if in_minute >= per_minute:
            raise MailLimitError(f"Per minute limit ({per_minute}) exceeded.")

        in_hour = mail.db.session.query(sa.func.count(cls))\
            .filter(cls.sent_at > now - dt.timedelta(hours=1))\
            .first()\
            .scalar()
        if in_hour >= per_hour:
            raise MailLimitError(f"Hourly limit ({per_hour}) exceeded.")

        in_day = mail.db.session.query(sa.func.count(cls))\
            .filter(cls.sent_at > now - dt.timedelta(days=1))\
            .first()\
            .scalar()
        if in_day >= per_day:
            raise MailLimitError(f"Daily limit ({per_day}) exceeded.")

    @classmethod
    def unsent(cls):
        qry = getattr(cls, 'qry')
        return qry.filter_by(sent_at=None)

    @classmethod
    def scheduled(cls):
        return cls.unsent().filter(cls.scheduled_at < dt.datetime.utcnow())

    def send(self, connection):
        type(self).check_limit()

        msg = self.message

        try:
            if connection is not None:
                connection.send(msg)
            else:
                mail.send(msg)
            self.sent_at = dt.datetime.utcnow()
            db.session.commit()
        except (SMTPDataError, SMTPSenderRefused, SMTPRecipientsRefused) as e:
            self.sent_at = dt.datetime.utcnow()
            self.error = str(e)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def send_scheduled(cls):
        with mail.connection() as conn:
            for email in cls.scheduled().all():
                try:
                    email.send(conn)
                except MailLimitError:
                    break
                except Exception:
                    continue
