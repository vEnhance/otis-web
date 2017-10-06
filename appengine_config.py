from google.appengine.ext import vendor
vendor.add('lib')
# To use, run
# pip2 install -t lib -r requirements-vendor.txt


# https://github.com/jschneier/django-storages/issues/281
# Monkey fix...
import tempfile
tempfile.SpooledTemporaryFile = tempfile.TemporaryFile
