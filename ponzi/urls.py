from django.urls import path

from . import views

urlpatterns = [
    path(r"", views.PonziSchemeList.as_view(), name="ponzi-list"),
    path(r"<int:pk>/", views.scheme_detail, name="ponzi-scheme"),
    path(r"<int:pk>/invest/", views.invest, name="ponzi-invest"),
    path(r"upgrade/<int:pk>/", views.upgrade, name="ponzi-upgrade"),
    path(r"withdraw/<int:pk>/", views.withdraw, name="ponzi-withdraw"),
]
