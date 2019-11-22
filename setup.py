from setuptools import setup

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='Flask-MailAlchemy',
    version='0.3',
    packages=['flask_mailalchemy'],
    url='https://github.com/gerelorant/flask-mailalchemy',
    license='MIT',
    author='Gere Lóránt',
    author_email='gerelorant@gmail.com',
    description='SQLAlchemy based e-mail sending extension for Flask',
    install_requires=['Flask', "Flask-Mail", "Flask-SQLAlchemy"],
    include_package_data=True,
    long_description=long_description,
    long_description_content_type='text/markdown'
)
