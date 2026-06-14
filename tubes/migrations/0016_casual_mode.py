from django.db import migrations, models


def spoil_before_to_casual(apps, schema_editor):
    """Carry over existing spoiled contributors into casual mode.

    A contributor who had ``spoil_before`` set had already seen the answers and
    solutions of every problem created up to that timestamp, so we both flip them
    into casual mode and pre-reveal those proposals to preserve what they could
    already see.
    """
    OIMEContributor = apps.get_model("tubes", "OIMEContributor")
    OIMEProposal = apps.get_model("tubes", "OIMEProposal")
    for contributor in OIMEContributor.objects.exclude(spoil_before=None):
        contributor.casual_mode = True
        contributor.save(update_fields=["casual_mode"])
        already_seen = OIMEProposal.objects.filter(
            created_at__lte=contributor.spoil_before
        )
        contributor.revealed_proposals.add(*already_seen)


class Migration(migrations.Migration):
    dependencies = [
        ("tubes", "0015_alter_oimefight_contributor_alter_oimefight_proposal"),
    ]

    operations = [
        migrations.AddField(
            model_name="oimecontributor",
            name="casual_mode",
            field=models.BooleanField(
                default=False,
                help_text="If set, this contributor browses casually: they can view every "
                "problem statement untimed and upvote, nothing is recorded, and they can no "
                "longer start timed sessions. Solutions stay hidden until revealed per-problem.",
            ),
        ),
        migrations.AddField(
            model_name="oimecontributor",
            name="revealed_proposals",
            field=models.ManyToManyField(
                blank=True,
                help_text="Proposals whose solution this contributor has chosen to reveal.",
                related_name="revealed_by",
                to="tubes.oimeproposal",
            ),
        ),
        migrations.RunPython(spoil_before_to_casual, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="oimecontributor",
            name="spoil_before",
        ),
    ]
