import datetime as dt
import threading as th
import time as tm

from flask import Flask, Blueprint, render_template
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

from flask_mailalchemy.model import EmailMixin


class MailAlchemy:
    def __init__(self, app: Flask = None, db: SQLAlchemy = None):
        self.app = app
        self.db = db
        self.mail = None
        self.email_class = None
        self.__stop_worker__ = False

        if app is not None:
            self.init_app(app, db)

    def init_app(self, app: Flask, db: SQLAlchemy):
        self.app = app
        self.db = db
        self.mail = Mail(self.app)

        class Email(db.Model, EmailMixin):
            pass

        self.email_class = Email

        self.app.register_blueprint(
            Blueprint("mail", __name__, template_folder="mail")
        )

    def send(self, msg: Message):
        for email in self.email_class.from_message(msg):
            self.db.session.add(email)
            email.send()
        self.db.session.commit()

    def send_message(self, *args, **kwargs):
        msg = Message(*args, **kwargs)
        self.send(msg)

    def render_template(self, msg: Message, template: str, **context):
        try:
            msg.body = render_template(template + ".txt", **context)
        except FileNotFoundError:
            pass

        try:
            msg.html = render_template(template + ".html", **context)
        except FileNotFoundError:
            pass

    def schedule(self, msg: Message, scheduled_at: dt.datetime = None):
        if scheduled_at is None:
            scheduled_at = dt.datetime.utcnow()
        for email in self.email_class.from_message(msg):
            email.scheduled_at = scheduled_at
            self.db.session.add(email)

    def schedule_message(
            self,
            *args,
            scheduled_at:
            dt.datetime = None,
            **kwargs
    ):
        msg = Message(*args, **kwargs)
        self.schedule(msg, scheduled_at=scheduled_at)

    def worker(self):
        with self.app.app_context():
            while not self.__stop_worker__:
                self.email_class.send_scheduled()
                tm.sleep(self.app.config.get("MAIL_ALCHEMY_CYCLE", 10))

    def run_worker(self):
        thread = th.Thread(target=self.worker)
        thread.start()

    def stop_worker(self):
        self.__stop_worker__ = True
