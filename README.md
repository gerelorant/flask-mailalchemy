# Flask-MailAlchemy
SQLAlchemy based e-mail sending extension for Flask.

## Usage

The provided MailAlchemy extension object registers a Flask-Mail instance and an
Email model class through Flask-SQLAlchemy.

Flask-MailAlchemy can be configured with the same parameters as 
[Flask-Mail](https://pythonhosted.org/Flask-Mail/#configuring-flask-mail)
Additional parameters include `MAIL_PER_MINUTE`, `MAIL_PER_HOUR` and 
`MAIL_PER_DAY`.

### Initialize

The MailAlchemy extension can be initialized like any other Flask extension.
Flask-SQLAlchemy instance is needed. Custom Email model can be provided for
extending the model with extra functionality (e.g.: Adding foreign key to user
table). If `email_class` is `None`, a simple Email model is used. You can also 
provide the Flask app after initialization with `mail.init_app(app)`. 
```python
from flask import Flask
from flask_mailalchemy import MailAlchemy, Message, EmailMixin
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy(app)


class Email(db.Model, EmailMixin):
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    

mail = MailAlchemy(app, db, Email)


if __name__ == '__main__':
    app.run()
```
 
 ### Sending mails
 To send email instantly, use the `send()` or `send_message()` methods just like
 in Flask-Mail. Additionally, message content can be rendered from templates 
 with the `render_template()` method.
 Templates should be saved in the `templates/mail/` directory. The method expects 
 the template name without extension and uses `.html` and `.txt` files for 
 message body.
 ```python
msg = Message(
    subject="Test Mail",
    sender=("Sender Name", "sender@address.com"),
    recipients=("recipient1@example.com", "recipient2@example.com")
)
mail.render_template(msg, "hello_world", name="John")

mail.send(msg)
```

### Using worker
It might be a good idea to handle the sending of e-mails in the background in a
separate thread. This way we can schedule e-mails to be sent at a specific time
in the future and handle mail server limitations. These limitations can be set
in the Flask config with the values `MAIL_PER_MINUTE`, `MAIL_PER_HOUR` and 
`MAIL_PER_DAY`. To schedule an e-mail to send, use the `schedule()` or 
`schedule_mesage()`  methods.
```python
@app.route("/mail_test")
def mail_test():
    msg = Message(
        subject="Test Mail",
        sender=("Sender Name", "sender@address.com"),
        recipients=("recipient1@example.com", "recipient2@example.com")
    )
    mail.render_template(msg, "hello_world", name="John")
    
    mail.schedule(msg, datetime.datetime(2020, 1, 1, 8, 0, 0))

if __name__ == '__main__':
    mail.run_worker()
    app.run()
```

### Templates
There is a base template available in the `templates/mail/` directory, which is
consists of 4 regular blocks and one content block.
```jinja2
{% block header %}{% include "mail/blocks/header.html" %}{% endblock %}

{% block greetings %}{% include "mail/blocks/greetings.html" %}{% endblock %}

{% block content%}{% endblock %}

{% block sign_off %}{% include "mail/blocks/sign_off.html" %}{% endblock %}

{% block footer %}{% include "mail/blocks/footer.html" %}{% endblock %}
```
The regular blocks are found in `templates/mail/blocks`. The base and block 
templates have both an HTML and a plaintext version. For your e-mail templates
simply extend the base template and override the `content` block.
```jinja2
{% extends 'mail/base.html' %}

{% block content %}
<p>Hello {{name}}!</p>
{% endblock %}
``` 