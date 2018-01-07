from google.appengine.ext import vendor
# This requires you to install requirements.txt in a venv
vendor.add('venv/lib/python2.7/site-packages')

# https://github.com/jschneier/django-storages/issues/281
# Monkey fix...
import tempfile
tempfile.SpooledTemporaryFile = tempfile.TemporaryFile
tempfile.NamedTemporaryFile = tempfile.TemporaryFile
