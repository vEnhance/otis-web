import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_users(apps, schema_editor):
    PonziInvestment = apps.get_model("ponzi", "PonziInvestment")
    PonziScheme = apps.get_model("ponzi", "PonziScheme")
    for investment in PonziInvestment.objects.select_related("student"):
        investment.user_id = investment.student.user_id
        investment.save(update_fields=["user"])
    for scheme in PonziScheme.objects.filter(collapsed_by__isnull=False).select_related(
        "collapsed_by"
    ):
        scheme.collapsed_by_user_id = scheme.collapsed_by.user_id
        scheme.save(update_fields=["collapsed_by_user"])


class Migration(migrations.Migration):
    dependencies = [
        ("ponzi", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ponziinvestment",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="ponzischeme",
            name="collapsed_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(copy_users, migrations.RunPython.noop),
        migrations.RemoveField(model_name="ponziinvestment", name="student"),
        migrations.RemoveField(model_name="ponzischeme", name="collapsed_by"),
        migrations.RemoveField(model_name="ponzischeme", name="semester"),
        migrations.AlterField(
            model_name="ponziinvestment",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RenameField(
            model_name="ponzischeme",
            old_name="collapsed_by_user",
            new_name="collapsed_by",
        ),
        migrations.AlterField(
            model_name="ponzischeme",
            name="collapsed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="The user whose withdrawal broke the bank",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
