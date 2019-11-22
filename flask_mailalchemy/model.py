import datetime as dt
from smtplib import SMTPDataError, SMTPSenderRefused, SMTPRecipientsRefused

from flask import current_app
from flask_mail import Message, Connection
import sqlalchemy as sa
from werkzeug.local import LocalProxy


db = LocalProxy(lambda: current_app.extensions.get("sqlalchemy").db)
config = LocalProxy(lambda: current_app.config)
mail = LocalProxy(lambda: current_app.extensions.get("mail"))
mail_alchemy = LocalProxy(lambda: current_app.extensions.get("mail_alchemy"))


class MailNotSetError(Exception):
    pass


class MailLimitError(Exception):
    pass


class AttachmentMixin:
    """Declarative mixin class for e-mail attachments."""
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
    filename = sa.Column(sa.String(255))
    content_type = sa.Column(sa.String(40))
    data = sa.Column(sa.LargeBinary)


class EmailMixin:
    """Declarative mixin class for e-mail table."""
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
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
        index=True
    )
    error = sa.Column(sa.Text)

    @property
    def message(self) -> Message:
        sender = self.sender_address \
            if self.sender_name is None \
            else (self.sender_name, self.sender_address)
        msg = Message(
            self.subject,
            [self.recipient],
            self.message_txt,
            self.message_html,
            sender
        )

        if hasattr(self, "attachments"):
            for attachment in self.attachments:
                msg.attach(
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    data=attachment.data
                )

        return msg

    @classmethod
    def from_message(cls, msg: Message) -> tuple:
        messages = []
        if isinstance(msg.recipients, str):
            recipients = [msg.recipients]
        else:
            recipients = msg.recipients

        if msg.sender.endswith(">"):
            separator = msg.sender.rfind("<")
            sender_address = msg.sender[separator+1:-1]
            sender_name = msg.sender[:separator].strip()
        else:
            sender_address = msg.sender
            sender_name = None

        subject = msg.subject
        message_html = msg.html
        message_txt = msg.body

        attachments = []
        if hasattr(cls, "attachments"):
            for a in msg.attachments:
                attachment = mail_alchemy.attachment_class()
                attachment.filename = a.filename
                attachment.content_type = a.content_type
                attachment.data = a.data
                db.session.add(attachment)
                attachments.append(attachment)

        for recipient in recipients:
            email = cls()
            email.recipient = recipient
            email.sender_address = sender_address
            email.sender_name = sender_name
            email.subject = subject
            email.message_html = message_html
            email.message_txt = message_txt

            if hasattr(email, "attachments"):
                email.attachments.extend(attachments)

            messages.append(email)

        return tuple(messages)

    @classmethod
    def check_limit(cls):
        per_minute = config.get("MAIL_PER_MINUTE", None)
        per_hour = config.get("MAIL_PER_HOUR", None)
        per_day = config.get("MAIL_PER_DAY", None)

        now = dt.datetime.utcnow()

        qry = db.session.query(sa.func.count(cls.id))\
            .filter(cls.sent_at != None)\

        if per_minute is not None:
            in_minute = qry\
                .filter(cls.sent_at > now - dt.timedelta(minutes=1))\
                .first()[0] or 0
            if in_minute >= per_minute:
                raise MailLimitError(
                    f"Per minute limit ({per_minute}) exceeded."
                )

        if per_hour is not None:
            in_hour = qry\
                .filter(cls.sent_at > now - dt.timedelta(hours=1))\
                .first()\
                .first()[0] or 0
            if in_hour >= per_hour:
                raise MailLimitError(f"Hourly limit ({per_hour}) exceeded.")

        if per_day is not None:
            in_day = qry\
                .filter(cls.sent_at > now - dt.timedelta(days=1))\
                .first()\
                .first()[0] or 0
            if in_day >= per_day:
                raise MailLimitError(f"Daily limit ({per_day}) exceeded.")

    @classmethod
    def unsent(cls):
        qry = getattr(cls, 'query')
        return qry.filter_by(sent_at=None)

    @classmethod
    def scheduled(cls):
        return cls.unsent().filter(cls.scheduled_at < dt.datetime.utcnow())

    def send(self, connection: Connection = None):
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
        with mail.connect() as conn:
            for email in cls.scheduled().all():
                try:
                    email.send(conn)
                except MailLimitError:
                    break
                except Exception:
                    continue
