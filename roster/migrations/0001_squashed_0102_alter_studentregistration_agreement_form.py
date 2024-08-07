# Generated by Django 4.1.10 on 2023-08-10 20:35

import datetime

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import roster.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_squashed_0054_userprofile_use_twemoji"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Assistant",
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
                    "user",
                    models.OneToOneField(
                        default=1,
                        help_text="The Django Auth user attached to the Assistant.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "shortname",
                    models.CharField(
                        default="??",
                        help_text="Initials or short name for this Assistant",
                        max_length=10,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Student",
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
                    "curriculum",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The choice of units that this student will work on",
                        related_name="students_taking",
                        to="core.unit",
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        help_text="The semester for this student",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.semester",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        default=1,
                        help_text="The Django auth user attached to the student",
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assistant",
                    models.ForeignKey(
                        blank=True,
                        help_text="The assistant for this student, if any",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="roster.assistant",
                    ),
                ),
                (
                    "legit",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this student is still active. Set to false for dummy accounts and the like. This will hide them from the master schedule, for example.",
                    ),
                ),
                (
                    "track",
                    models.CharField(
                        choices=[
                            ("A", "Weekly"),
                            ("B", "Biweekly"),
                            ("C", "Corr."),
                            ("E", "Ext."),
                            ("G", "Grad"),
                            ("N", "N.A."),
                            ("P", "Phantom"),
                        ],
                        help_text="The track that the student is enrolled in for this semester.",
                        max_length=5,
                    ),
                ),
                (
                    "unlocked_units",
                    models.ManyToManyField(
                        blank=True,
                        help_text="A list of units that the student is actively working on. Once the student submits a problem set, delete it from this list to mark them as complete.",
                        related_name="students_unlocked",
                        to="core.unit",
                    ),
                ),
                (
                    "newborn",
                    models.BooleanField(
                        default=True, help_text="Whether the student is newly created."
                    ),
                ),
                (
                    "last_level_seen",
                    models.PositiveSmallIntegerField(
                        default=0, help_text="The last level the student was seen at."
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True, help_text="Allow student to submit/request units."
                    ),
                ),
            ],
            options={
                "ordering": (
                    "semester",
                    "-legit",
                    "track",
                    "user__first_name",
                    "user__last_name",
                ),
                "unique_together": {("user", "semester")},
            },
        ),
        migrations.AddField(
            model_name="assistant",
            name="unlisted_students",
            field=models.ManyToManyField(
                blank=True,
                help_text="A list of students this assistant can see but which is not listed visibly.",
                related_name="unlisted_assistants",
                to="roster.student",
            ),
        ),
        migrations.CreateModel(
            name="RegistrationContainer",
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
                    "passcode",
                    models.CharField(
                        help_text="The passcode for that year's registration",
                        max_length=128,
                    ),
                ),
                (
                    "semester",
                    models.OneToOneField(
                        help_text="Controls the settings for registering for a semester",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.semester",
                    ),
                ),
                (
                    "accepting_responses",
                    models.BooleanField(
                        default=False,
                        help_text="Whether responses for this year are being accepted or not.",
                    ),
                ),
            ],
        ),
        migrations.AlterModelOptions(
            name="assistant",
            options={"ordering": ("shortname",)},
        ),
        migrations.CreateModel(
            name="StudentRegistration",
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
                    "parent_email",
                    models.EmailField(
                        help_text="An email address in case Evan needs to contact your parents or something.",
                        max_length=254,
                    ),
                ),
                (
                    "gender",
                    models.CharField(
                        choices=[
                            ("M", "Male"),
                            ("F", "Female"),
                            ("H", "Nonbinary"),
                            ("O", "Other"),
                            ("U", "Prefer not to say"),
                        ],
                        default="",
                        help_text="If you are comfortable answering, specify which gender you most closely identify with.",
                        max_length=2,
                    ),
                ),
                (
                    "school_name",
                    models.CharField(
                        help_text="Enter the name of your high school", max_length=200
                    ),
                ),
                (
                    "aops_username",
                    models.CharField(
                        blank=True,
                        help_text="Enter your Art of Problem Solving username (leave blank for none)",
                        max_length=200,
                    ),
                ),
                (
                    "agreement_form",
                    models.FileField(
                        help_text="Signed decision form, as a single PDF",
                        null=True,
                        upload_to=roster.models.content_file_name,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["pdf"]
                            )
                        ],
                        verbose_name="Decision form",
                    ),
                ),
                (
                    "container",
                    models.ForeignKey(
                        help_text="Where to register for",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.registrationcontainer",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="The user to attach",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="regs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "processed",
                    models.BooleanField(
                        default=False,
                        help_text="Whether Evan has dealt with this kid yet",
                    ),
                ),
                (
                    "graduation_year",
                    models.IntegerField(
                        choices=[
                            (0, "Already graduated high school"),
                            (2021, "Graduating in 2021"),
                            (2022, "Graduating in 2022"),
                            (2023, "Graduating in 2023"),
                            (2024, "Graduating in 2024"),
                            (2025, "Graduating in 2025"),
                            (2026, "Graduating in 2026"),
                            (2027, "Graduating in 2027"),
                            (2028, "Graduating in 2028"),
                            (2029, "Graduating in 2029"),
                        ],
                        help_text="Enter your expected graduation year",
                    ),
                ),
                (
                    "country",
                    models.CharField(
                        choices=[
                            ("AFG", "Afghanistan (AFG)"),
                            ("ALB", "Albania (ALB)"),
                            ("ALG", "Algeria (ALG)"),
                            ("AGO", "Angola (AGO)"),
                            ("ARG", "Argentina (ARG)"),
                            ("ARM", "Armenia (ARM)"),
                            ("AUS", "Australia (AUS)"),
                            ("AUT", "Austria (AUT)"),
                            ("AZE", "Azerbaijan (AZE)"),
                            ("BAH", "Bahrain (BAH)"),
                            ("BGD", "Bangladesh (BGD)"),
                            ("BLR", "Belarus (BLR)"),
                            ("BEL", "Belgium (BEL)"),
                            ("BEN", "Benin (BEN)"),
                            ("BOL", "Bolivia (BOL)"),
                            ("BIH", "Bosnia and Herzegovina (BIH)"),
                            ("BWA", "Botswana (BWA)"),
                            ("BRA", "Brazil (BRA)"),
                            ("BRU", "Brunei (BRU)"),
                            ("BGR", "Bulgaria (BGR)"),
                            ("BFA", "Burkina Faso (BFA)"),
                            ("KHM", "Cambodia (KHM)"),
                            ("CAN", "Canada (CAN)"),
                            ("CHI", "Chile (CHI)"),
                            ("CHN", "People's Republic of China (CHN)"),
                            ("COL", "Colombia (COL)"),
                            ("CIS", "Commonwealth of Independent States (CIS)"),
                            ("CRI", "Costa Rica (CRI)"),
                            ("HRV", "Croatia (HRV)"),
                            ("CUB", "Cuba (CUB)"),
                            ("CYP", "Cyprus (CYP)"),
                            ("CZE", "Czech Republic (CZE)"),
                            ("CZS", "Czechoslovakia (CZS)"),
                            ("DEN", "Denmark (DEN)"),
                            ("DOM", "Dominican Republic (DOM)"),
                            ("ECU", "Ecuador (ECU)"),
                            ("EGY", "Egypt (EGY)"),
                            ("EST", "Estonia (EST)"),
                            ("FIN", "Finland (FIN)"),
                            ("FRA", "France (FRA)"),
                            ("GMB", "Gambia (GMB)"),
                            ("GEO", "Georgia (GEO)"),
                            ("GDR", "German Democratic Republic (GDR)"),
                            ("GER", "Germany (GER)"),
                            ("GHA", "Ghana (GHA)"),
                            ("HEL", "Greece (HEL)"),
                            ("GTM", "Guatemala (GTM)"),
                            ("HND", "Honduras (HND)"),
                            ("HKG", "Hong Kong (HKG)"),
                            ("HUN", "Hungary (HUN)"),
                            ("ISL", "Iceland (ISL)"),
                            ("IND", "India (IND)"),
                            ("IDN", "Indonesia (IDN)"),
                            ("IRQ", "Iraq (IRQ)"),
                            ("IRN", "Islamic Republic of Iran (IRN)"),
                            ("IRL", "Ireland (IRL)"),
                            ("ISR", "Israel (ISR)"),
                            ("ITA", "Italy (ITA)"),
                            ("CIV", "Ivory Coast (CIV)"),
                            ("JAM", "Jamaica (JAM)"),
                            ("JPN", "Japan (JPN)"),
                            ("KAZ", "Kazakhstan (KAZ)"),
                            ("KEN", "Kenya (KEN)"),
                            ("PRK", "Democratic People's Republic of Korea (PRK)"),
                            ("KOR", "Republic of Korea (KOR)"),
                            ("KSV", "Kosovo (KSV)"),
                            ("KWT", "Kuwait (KWT)"),
                            ("KGZ", "Kyrgyzstan (KGZ)"),
                            ("LAO", "Laos (LAO)"),
                            ("LVA", "Latvia (LVA)"),
                            ("LIE", "Liechtenstein (LIE)"),
                            ("LTU", "Lithuania (LTU)"),
                            ("LUX", "Luxembourg (LUX)"),
                            ("MAC", "Macau (MAC)"),
                            ("MDG", "Madagascar (MDG)"),
                            ("MAS", "Malaysia (MAS)"),
                            ("MRT", "Mauritania (MRT)"),
                            ("MEX", "Mexico (MEX)"),
                            ("MDA", "Republic of Moldova (MDA)"),
                            ("MNG", "Mongolia (MNG)"),
                            ("MNE", "Montenegro (MNE)"),
                            ("MAR", "Morocco (MAR)"),
                            ("MOZ", "Mozambique (MOZ)"),
                            ("MMR", "Myanmar (MMR)"),
                            ("NPL", "Nepal (NPL)"),
                            ("NLD", "Netherlands (NLD)"),
                            ("NZL", "New Zealand (NZL)"),
                            ("NIC", "Nicaragua (NIC)"),
                            ("NGA", "Nigeria (NGA)"),
                            ("MKD", "North Macedonia (MKD)"),
                            ("NOR", "Norway (NOR)"),
                            ("OMN", "Oman (OMN)"),
                            ("PAK", "Pakistan (PAK)"),
                            ("PAN", "Panama (PAN)"),
                            ("PAR", "Paraguay (PAR)"),
                            ("PER", "Peru (PER)"),
                            ("PHI", "Philippines (PHI)"),
                            ("POL", "Poland (POL)"),
                            ("POR", "Portugal (POR)"),
                            ("PRI", "Puerto Rico (PRI)"),
                            ("ROU", "Romania (ROU)"),
                            ("RUS", "Russian Federation (RUS)"),
                            ("RWA", "Rwanda (RWA)"),
                            ("SLV", "El Salvador (SLV)"),
                            ("SAU", "Saudi Arabia (SAU)"),
                            ("SEN", "Senegal (SEN)"),
                            ("SRB", "Serbia (SRB)"),
                            ("SCG", "Serbia and Montenegro (SCG)"),
                            ("SGP", "Singapore (SGP)"),
                            ("SVK", "Slovakia (SVK)"),
                            ("SVN", "Slovenia (SVN)"),
                            ("SAF", "South Africa (SAF)"),
                            ("ESP", "Spain (ESP)"),
                            ("LKA", "Sri Lanka (LKA)"),
                            ("SWE", "Sweden (SWE)"),
                            ("SUI", "Switzerland (SUI)"),
                            ("SYR", "Syria (SYR)"),
                            ("TWN", "Taiwan (TWN)"),
                            ("TJK", "Tajikistan (TJK)"),
                            ("TZA", "Tanzania (TZA)"),
                            ("THA", "Thailand (THA)"),
                            ("TTO", "Trinidad and Tobago (TTO)"),
                            ("TUN", "Tunisia (TUN)"),
                            ("TUR", "Turkey (TUR)"),
                            ("NCY", "Turkish Republic of Northern Cyprus (NCY)"),
                            ("TKM", "Turkmenistan (TKM)"),
                            ("UGA", "Uganda (UGA)"),
                            ("UKR", "Ukraine (UKR)"),
                            ("UAE", "United Arab Emirates (UAE)"),
                            ("UNK", "United Kingdom (UNK)"),
                            ("USA", "United States of America (USA)"),
                            ("URY", "Uruguay (URY)"),
                            ("USS", "Union of Soviet Socialist Republics (USS)"),
                            ("UZB", "Uzbekistan (UZB)"),
                            ("VEN", "Venezuela (VEN)"),
                            ("VNM", "Vietnam (VNM)"),
                            ("YEM", "Yemen (YEM)"),
                            ("YUG", "Yugoslavia (YUG)"),
                            ("ZWE", "Zimbabwe (ZWE)"),
                        ],
                        default="USA",
                        max_length=6,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, default=django.utils.timezone.now
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "container")},
            },
        ),
        migrations.AddField(
            model_name="student",
            name="reg",
            field=models.OneToOneField(
                blank=True,
                help_text="Link to the registration forms for the student",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="roster.studentregistration",
            ),
        ),
        migrations.CreateModel(
            name="UnitInquiry",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("INQ_ACT_UNLOCK", "Unlock now"),
                            ("INQ_ACT_APPEND", "Add for later"),
                            ("INQ_ACT_DROP", "Drop"),
                            ("INQ_ACT_LOCK", "Lock (Drop + Add for later)"),
                        ],
                        help_text="Describe the action you want to make.",
                        max_length=15,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("INQ_ACC", "Accepted"),
                            ("INQ_REJ", "Rejected"),
                            ("INQ_NEW", "Pending"),
                            ("INQ_HOLD", "On hold"),
                        ],
                        default="INQ_NEW",
                        help_text="The current status of the petition.",
                        max_length=10,
                    ),
                ),
                (
                    "explanation",
                    models.TextField(
                        help_text="Short explanation for this request.", max_length=300
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        help_text="The student making the request",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        help_text="The unit being requested.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.unit",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
                "verbose_name": "Unit petition",
                "verbose_name_plural": "Unit petitions",
            },
        ),
        migrations.CreateModel(
            name="Invoice",
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
                    "preps_taught",
                    models.SmallIntegerField(
                        default=0,
                        help_text="Number of semesters that development/preparation costs are charged.",
                    ),
                ),
                (
                    "hours_taught",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Number of hours taught for.",
                        max_digits=8,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.OneToOneField(
                        help_text="The invoice that this student is for.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="roster.student",
                    ),
                ),
                (
                    "total_paid",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Amount paid.",
                        max_digits=8,
                    ),
                ),
                (
                    "adjustment",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Adjustment to the cost, e.g. for financial aid.",
                        max_digits=8,
                    ),
                ),
                (
                    "extras",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Additional payment, e.g. for T-shirts.",
                        max_digits=8,
                    ),
                ),
                (
                    "memo",
                    models.TextField(blank=True, help_text="Internal note to self."),
                ),
                (
                    "forgive_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="When switched on, won't hard lock delinquents before this date.",
                        null=True,
                    ),
                ),
                (
                    "credits",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Credit earned via internships",
                        max_digits=8,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        default=datetime.datetime(
                            1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
                        ),
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="assistant",
            name="shortname",
            field=models.CharField(
                help_text="Initials or short name for this Assistant", max_length=18
            ),
        ),
        migrations.AlterModelOptions(
            name="student",
            options={
                "ordering": (
                    "semester",
                    "-legit",
                    "user__first_name",
                    "user__last_name",
                )
            },
        ),
        migrations.RemoveField(
            model_name="student",
            name="track",
        ),
    ]
