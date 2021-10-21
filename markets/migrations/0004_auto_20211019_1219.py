# Generated by Django 3.2.8 on 2021-10-19 16:19

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('markets', '0003_alter_guess_public'),
    ]

    operations = [
        migrations.AlterField(
            model_name='market',
            name='alpha',
            field=models.FloatField(default=1, help_text='Exponent corresponding to harshness of the market,  used in the scoring function'),
        ),
        migrations.AlterUniqueTogether(
            name='guess',
            unique_together={('user', 'market')},
        ),
    ]
