import datetime as dt
import threading as th
import time as tm

from flask import Flask, Blueprint, render_template
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

from flask_mailalchemy.model import EmailMixin


class MailAlchemy:
    """Flask-MailAlchemy extension

    Manages mail sending with scheduling and email sending limits.

    Args:
        app: Flask instance
        db: SQLAlchemy instance
        email_class: Email model class

    """
    def __init__(
            self,
            app: Flask = None,
            db: SQLAlchemy = None,
            email_class: type(EmailMixin) = None
    ):
        self.app = app
        self.db = db
        self.mail = None
        self.email_class = email_class
        self.__stop_worker__ = False

        if app is not None:
            self.init_app(app, db)

    def init_app(
            self,
            app: Flask,
            db: SQLAlchemy,
            email_class: type(EmailMixin) = None
    ):
        """Initialize Flask-MailAlchemy

        Initializes Flask-Mail instance, creates email model class and registers
        blueprint `mail`.

        Args:
            app: Flask instance
            db: SQLAlchemy instance
            email_class: Email model class

        """
        self.app = app

        if db is None:
            db = app.extensions.get("sqlalchemy").db
        self.db = db

        self.mail = Mail(self.app)

        self.email_class = self.email_class or email_class
        if self.email_class is None:
            class Email(db.Model, EmailMixin):
                pass

            self.email_class = Email

        self.app.register_blueprint(
            Blueprint("mail", __name__, url_prefix='/mail', template_folder="templates")
        )

    def send(self, msg: Message):
        """Sends a single message instance.

        Stores messages in database and sends them. A separate message is stored
        for every recipient in database. If TESTING is True the message will not
        actually be sent.

        Args:
            msg: a Message instance.
        """
        emails = self.email_class.from_message(msg)
        for email in emails:
            self.db.session.add(email)
            self.db.session.commit()

        for email in emails:
            email.send()
            self.db.session.commit()

    def send_message(self, *args, **kwargs):
        """Shortcut for send(msg).

        Takes same arguments as Message constructor.

        """
        msg = Message(*args, **kwargs)
        self.send(msg)

    def render_template(self, msg: Message, template: str, **context):
        """Renders plaintext and HTML content for Message.

        Message body is set from template found with .txt ending, html is set
        from template found with .html ending.

        Args:
            msg: Message instance
            template: Template name without extension
            **context: Template context

        """
        try:
            msg.body = render_template(f"mail/{template}.txt", **context)
        except FileNotFoundError:
            pass

        try:
            msg.html = render_template(f"mail/{template}.html", **context)
        except FileNotFoundError:
            pass

    def schedule(self, msg: Message, scheduled_at: dt.datetime = None):
        """Schedules a single message instance to send in future.

        Stores messages in database and sends them. A separate message is stored
        for every recipient in database.

        Args:
            msg: Message instance
            scheduled_at: Time of sending in future

        """
        if scheduled_at is None:
            scheduled_at = dt.datetime.utcnow()
        for email in self.email_class.from_message(msg):
            email.scheduled_at = scheduled_at
            self.db.session.add(email)

        self.db.session.commit()

    def schedule_message(
            self,
            *args,
            scheduled_at: dt.datetime = None,
            **kwargs
    ):
        """Shortcut for schedule(msg).

        Takes same arguments as Message constructor plus the `scheduled_at`
        datetime parameter.

        """
        msg = Message(*args, **kwargs)
        self.schedule(msg, scheduled_at=scheduled_at)

    def worker(self):
        """Sends unsent emails that are scheduled before current time."""
        with self.app.app_context():
            while not self.__stop_worker__:
                self.email_class.send_scheduled()
                tm.sleep(self.app.config.get("MAIL_ALCHEMY_CYCLE", 10))

    def run_worker(self):
        """Starts worker thread."""
        thread = th.Thread(target=self.worker)
        thread.start()

    def stop_worker(self):
        """Stops worker thread's loop."""
        self.__stop_worker__ = True
