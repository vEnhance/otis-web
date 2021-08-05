from django.urls import path

from . import views

urlpatterns = [
		path(r'quiz/<int:student_id>/<int:pk>', views.quiz, name='quiz'),
		]
