from django.urls import path

from . import views

urlpatterns = [
		path(r'solve/<int:student_id>/<int:pk>', views.attempt_exam, name='attempt-exam'),
		path(r'graded/<int:student_id>/<int:pk>', views.show_exam, name='show-exam'),
		]
