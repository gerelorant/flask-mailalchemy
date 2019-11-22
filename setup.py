from setuptools import setup

setup(
    name='Flask-MailAlchemy',
    version='0.1',
    packages=['flask_mailalchemy'],
    url='https://github.com/gerelorant/flask-mailalchemy',
    license='MIT',
    author='Gere Lóránt',
    author_email='gerelorant@gmail.com',
    description='SQLAlchemy based e-mail sending extension for Flask',
    install_requires=['Flask', "Flask-Mail", "Flask-SQLAlchemy"],
    include_package_data=True
)
