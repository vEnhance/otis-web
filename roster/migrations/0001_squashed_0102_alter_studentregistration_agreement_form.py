# Generated by Django 4.1.10 on 2023-08-10 20:35

import datetime

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import roster.models


class Migration(migrations.Migration):
    replaces = [
        ("roster", "0001_initial"),
        ("roster", "0002_auto_20170806_0016"),
        ("roster", "0003_student_current_unit_index"),
        ("roster", "0004_auto_20170806_0022"),
        ("roster", "0005_auto_20170806_0031"),
        ("roster", "0006_auto_20170806_0035"),
        ("roster", "0007_auto_20170806_0044"),
        ("roster", "0008_auto_20170806_0053"),
        ("roster", "0009_auto_20170808_1730"),
        ("roster", "0010_auto_20170813_1037"),
        ("roster", "0011_auto_20170813_1207"),
        ("roster", "0012_student_legit"),
        ("roster", "0013_invoice"),
        ("roster", "0014_auto_20171205_0924"),
        ("roster", "0015_auto_20171205_0939"),
        ("roster", "0016_auto_20180107_0911"),
        ("roster", "0017_auto_20180531_1217"),
        ("roster", "0018_auto_20180531_1222"),
        ("roster", "0019_auto_20180825_0156"),
        ("roster", "0020_assistant_shortname"),
        ("roster", "0021_auto_20180825_1843"),
        ("roster", "0022_auto_20181206_1148"),
        ("roster", "0023_auto_20190322_0810"),
        ("roster", "0024_auto_20190327_1911"),
        ("roster", "0025_auto_20190809_1211"),
        ("roster", "0026_auto_20191011_1224"),
        ("roster", "0027_auto_20191011_1232"),
        ("roster", "0028_auto_20191011_1408"),
        ("roster", "0029_auto_20191011_1931"),
        ("roster", "0030_auto_20191201_1055"),
        ("roster", "0031_auto_20191201_1112"),
        ("roster", "0032_student_newborn"),
        ("roster", "0033_auto_20191204_1030"),
        ("roster", "0034_auto_20191213_0912"),
        ("roster", "0035_auto_20191214_2320"),
        ("roster", "0036_auto_20200421_1159"),
        ("roster", "0037_auto_20200428_0838"),
        ("roster", "0038_auto_20200428_0839"),
        ("roster", "0039_unlock_units"),
        ("roster", "0040_auto_20200428_0914"),
        ("roster", "0041_auto_20200428_0950"),
        ("roster", "0042_inquiry_type_rename"),
        ("roster", "0043_auto_20200428_0954"),
        ("roster", "0044_auto_20200428_1004"),
        ("roster", "0045_auto_20200429_1042"),
        ("roster", "0046_invoice_adjustment"),
        ("roster", "0047_auto_20201114_1551"),
        ("roster", "0048_drop_ws_type"),
        ("roster", "0049_auto_20210111_1623"),
        ("roster", "0050_auto_20210213_1702"),
        ("roster", "0051_auto_20210410_1117"),
        ("roster", "0052_invoice_forgive"),
        ("roster", "0053_registrationcontainer_studentregistration"),
        ("roster", "0054_auto_20210727_1603"),
        ("roster", "0055_auto_20210727_1609"),
        ("roster", "0056_auto_20210727_1624"),
        ("roster", "0057_auto_20210727_1634"),
        ("roster", "0058_auto_20210727_1656"),
        ("roster", "0059_auto_20210727_1754"),
        ("roster", "0060_studentregistration_country"),
        ("roster", "0061_alter_registrationcontainer_allowed_tracks"),
        ("roster", "0062_student_achievements"),
        ("roster", "0063_alter_student_achievements"),
        ("roster", "0064_auto_20210805_1551"),
        ("roster", "0065_alter_studentregistration_agreement_form"),
        ("roster", "0066_alter_studentregistration_graduation_year"),
        ("roster", "0067_remove_student_num_units_done"),
        ("roster", "0068_remove_student_achievements"),
        ("roster", "0069_alter_studentregistration_agreement_form"),
        ("roster", "0070_auto_20210820_1259"),
        ("roster", "0071_remove_student_usemo_score"),
        ("roster", "0072_alter_unitinquiry_status"),
        ("roster", "0073_registrationcontainer_num_preps"),
        ("roster", "0074_auto_20210913_1711"),
        ("roster", "0075_remove_student_last_level_time"),
        ("roster", "0076_alter_studentregistration_track"),
        ("roster", "0077_alter_studentregistration_user"),
        ("roster", "0078_invoice_forgive_memo"),
        ("roster", "0079_alter_studentregistration_options"),
        ("roster", "0080_auto_20211020_0923"),
        ("roster", "0081_alter_student_user"),
        ("roster", "0082_student_enabled"),
        ("roster", "0083_rename_forgive_memo_invoice_memo"),
        ("roster", "0084_alter_invoice_memo"),
        ("roster", "0085_alter_studentregistration_gender_and_more"),
        ("roster", "0086_auto_20220805_1803"),
        ("roster", "0087_student_reg"),
        ("roster", "0088_auto_20220921_2323"),
        ("roster", "0089_alter_unitinquiry_status"),
        ("roster", "0090_auto_20220927_1628"),
        ("roster", "0091_remove_registrationcontainer_end_year"),
        ("roster", "0092_alter_unitinquiry_explanation"),
        ("roster", "0093_remove_invoice_forgive_invoice_forgive_date"),
        ("roster", "0094_invoice_credits"),
        ("roster", "0095_alter_unitinquiry_action_type_and_more"),
        ("roster", "0096_studentregistration_created_at"),
        ("roster", "0097_remove_registrationcontainer_num_preps"),
        ("roster", "0098_alter_unitinquiry_action_type"),
        ("roster", "0099_invoice_created_at"),
        ("roster", "0100_alter_student_options_and_more"),
        ("roster", "0101_registrationcontainer_accepting_responses"),
        ("roster", "0102_alter_studentregistration_agreement_form"),
    ]

    initial = True

    dependencies = [
        ("core", "0018_auto_20200908_1307"),
        ("core", "0003_auto_20170806_0009"),
        ("core", "0005_unit_subject"),
        ("core", "0038_semester_end_year"),
        ("core", "0014_auto_20190830_1219"),
        ("core", "0007_semester_show_invoices"),
        ("core", "0015_auto_20200314_1453"),
        ("core", "0024_alter_unitgroup_slug"),
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
