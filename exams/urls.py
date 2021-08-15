from django.urls import path

from . import views

urlpatterns = [
	path(r'pdf/<int:pk>/', views.pdf, name='exam-pdf'),
	path(r'quiz/<int:student_id>/<int:pk>', views.quiz, name='quiz'),
]
