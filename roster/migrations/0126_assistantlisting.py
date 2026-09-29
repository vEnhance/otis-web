import django.db.models.deletion
from django.db import migrations, models


def move_ads(apps, schema_editor):
    Assistant = apps.get_model("roster", "Assistant")
    AssistantListing = apps.get_model("roster", "AssistantListing")
    for assistant in Assistant.objects.all():
        if not (
            assistant.ad_enabled
            or assistant.ad_url
            or assistant.ad_email
            or assistant.ad_blurb
        ):
            continue
        listing = AssistantListing.objects.create(
            assistant=assistant,
            website=assistant.ad_url,
            email=assistant.ad_email,
            blurb=assistant.ad_blurb,
            offers_one_on_one=assistant.ad_enabled,
        )
        # auto_now_add and auto_now clobber these on create, but not on update()
        AssistantListing.objects.filter(pk=listing.pk).update(
            created_at=assistant.created_at, updated_at=assistant.updated_at
        )


def restore_ads(apps, schema_editor):
    Assistant = apps.get_model("roster", "Assistant")
    AssistantListing = apps.get_model("roster", "AssistantListing")
    for listing in AssistantListing.objects.all():
        Assistant.objects.filter(pk=listing.assistant_id).update(
            ad_enabled=listing.offers_one_on_one or listing.offers_group,
            ad_url=listing.website,
            ad_email=listing.email,
            ad_blurb=listing.blurb,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("roster", "0125_assistant_students"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantListing",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "website",
                    models.URLField(
                        blank=True,
                        help_text="A URL the instructor can provide if desired.",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        help_text="An email the instructor can provide for contact.",
                        max_length=254,
                    ),
                ),
                (
                    "syllabus_url",
                    models.URLField(
                        blank=True,
                        help_text="A link to an external syllabus, if any.",
                        verbose_name="syllabus URL",
                    ),
                ),
                (
                    "offers_one_on_one",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the instructor is taking students for 1:1 meetings.",
                        verbose_name="1:1 meetings available",
                    ),
                ),
                (
                    "offers_group",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the instructor is taking students for group meetings.",
                        verbose_name="group meetings available",
                    ),
                ),
                (
                    "time_zone",
                    models.CharField(
                        blank=True,
                        help_text="The instructor's time zone.",
                        max_length=64,
                    ),
                ),
                (
                    "availability",
                    models.CharField(
                        blank=True,
                        help_text='When the instructor is available, e.g. "weekend evenings".',
                        max_length=200,
                    ),
                ),
                (
                    "next_steps",
                    models.CharField(
                        blank=True,
                        help_text='What a student should do to get started, e.g. "Email me with your AoPS username and what you want to work on."',
                        max_length=500,
                        verbose_name="to connect further",
                    ),
                ),
                (
                    "blurb",
                    models.TextField(
                        blank=True,
                        help_text="Any other description the instructor wants to provide.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assistant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="listing",
                        to="roster.assistant",
                    ),
                ),
            ],
        ),
        migrations.RunPython(move_ads, restore_ads),
        migrations.RemoveField(model_name="assistant", name="ad_blurb"),
        migrations.RemoveField(model_name="assistant", name="ad_email"),
        migrations.RemoveField(model_name="assistant", name="ad_enabled"),
        migrations.RemoveField(model_name="assistant", name="ad_url"),
        migrations.RemoveField(model_name="assistant", name="created_at"),
        migrations.RemoveField(model_name="assistant", name="updated_at"),
    ]
