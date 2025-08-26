from django.shortcuts import redirect
from django.urls import path

from . import views

urlpatterns = [
    path(r"user/<str:username>/", views.username_lookup, name="username-lookup"),
    path(r"curriculum/<int:student_pk>/", views.curriculum, name="currshow"),
    path(r"finalize/<int:student_pk>/", views.finalize, name="finalize"),
    path(r"advance/<int:student_pk>/", views.advance, name="advance"),
    path(r"invoice/", views.invoice, name="invoice"),
    path(r"invoice/<int:student_pk>/", views.invoice, name="invoice"),
    path(r"master-schedule/", views.master_schedule, name="master-schedule"),
    path(r"edit-invoice/<int:pk>/", views.UpdateInvoice.as_view(), name="edit-invoice"),
    path(r"inquiry/<int:student_pk>/", views.inquiry, name="inquiry"),
    path(r"inquiry/cancel/<int:pk>/", views.cancel_inquiry, name="inquiry-cancel"),
    path(r"register/", views.register, name="register"),
    path(r"profile/", views.update_profile, name="update-profile"),
    path(r"giga-chart/<str:format_as>/", views.giga_chart, name="giga-chart"),
    path(
        r"mystery_unlock/easier/",
        lambda request: redirect("../../mystery-unlock/easier/"),
    ),
    path(
        r"mystery_unlock/harder/",
        lambda request: redirect("../../mystery-unlock/harder/"),
    ),
    path(r"mystery-unlock/easier/", views.unlock_rest_of_mystery, kwargs={"delta": 1}),
    path(r"mystery-unlock/harder/", views.unlock_rest_of_mystery, kwargs={"delta": 2}),
    path(r"instructors/", views.StudentAssistantList.as_view(), name="instructors"),
    path(r"link-assistant/", views.link_assistant, name="link-assistant"),
    path(r"discord-lookup/", views.discord_lookup, name="discord-lookup"),
    path(r"ais/", views.AdList.as_view(), name="ad-list"),
    path(r"advertise/", views.AdUpdate.as_view(), name="ad-update"),
]
