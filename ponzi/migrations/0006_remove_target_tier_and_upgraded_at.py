from django.db import migrations
from django.db.models import OuterRef, Subquery


def restore(apps, schema_editor):
    """Undo: copy the latest timer back onto the bid."""
    PonziInvestment = apps.get_model("ponzi", "PonziInvestment")
    PonziTimer = apps.get_model("ponzi", "PonziTimer")
    latest = PonziTimer.objects.filter(investment=OuterRef("pk")).order_by("-tier")
    for inv in PonziInvestment.objects.annotate(
        latest_tier=Subquery(latest.values("tier")[:1]),
        latest_start=Subquery(latest.values("started_at")[:1]),
    ):
        if inv.latest_tier is None:
            continue
        inv.target_tier = inv.latest_tier
        inv.upgraded_at = inv.latest_start if inv.latest_tier > 1 else None
        inv.save(update_fields=["target_tier", "upgraded_at"])


class Migration(migrations.Migration):
    """The timer log now records every tier and start time, so these
    duplicated it. Reversing re-adds both and refills them from the log."""

    dependencies = [
        ("ponzi", "0005_backfill_ponzitimer"),
    ]

    operations = [
        # listed first so that, when reversed, it runs after the fields are back
        migrations.RunPython(migrations.RunPython.noop, restore),
        migrations.RemoveField(model_name="ponziinvestment", name="target_tier"),
        migrations.RemoveField(model_name="ponziinvestment", name="upgraded_at"),
    ]
