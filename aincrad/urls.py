from django.urls import path

from . import views

urlpatterns = [
    path(r"api/", views.api, name="api"),
    path(r"api/opal-pdf/", views.opal_pdf_upload, name="opal-pdf-upload"),
]
