from django.contrib import admin
from .models import PaymentLog


# Register your models here.
@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
	list_display = (
		'invoice',
		'amount',
		'created_at',
	)
	list_filter = ('invoice__student__semester', )
	search_fields = (
		'invoice__student__user__first_name',
		'invoice__student__user__last_name',
		'invoice__student__user__username',
	)
