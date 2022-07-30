from django.db import models
from roster.models import Invoice

# Create your models here.


class PaymentLog(models.Model):
	amount = models.IntegerField(help_text="Amount paid")
	created_at = models.DateTimeField(auto_now_add=True)
	invoice = models.ForeignKey(
		Invoice,
		on_delete=models.CASCADE,
		help_text="The invoice this contributes towards",
	)

	def __str__(self) -> str:
		return self.created_at.strftime('%c')
