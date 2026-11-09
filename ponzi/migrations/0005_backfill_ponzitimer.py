from django.db import migrations


def backfill(apps, schema_editor):
    """Rebuild each existing bid's timers from created_at and upgraded_at.

    Those two fields pin down every timer except one: a tier III bid only
    remembers its latest upgrade, so when its tier II timer started is lost.
    We guess the earliest possible moment, i.e. that the owner upgraded as
    soon as the bid matured, and mark that row as inferred.
    """
    PonziInvestment = apps.get_model("ponzi", "PonziInvestment")
    PonziTimer = apps.get_model("ponzi", "PonziTimer")
    timers = []
    for inv in PonziInvestment.objects.select_related("scheme"):
        T = inv.scheme.gestation_period
        timers.append(PonziTimer(investment=inv, tier=1, started_at=inv.created_at))
        for tier in range(2, inv.target_tier + 1):
            if tier == inv.target_tier and inv.upgraded_at is not None:
                started_at, inferred = inv.upgraded_at, False
            else:
                started_at, inferred = inv.created_at + (tier - 1) * T, True
            timers.append(
                PonziTimer(
                    investment=inv, tier=tier, started_at=started_at, inferred=inferred
                )
            )
    PonziTimer.objects.bulk_create(timers)


class Migration(migrations.Migration):
    dependencies = [
        ("ponzi", "0004_ponzitimer"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
