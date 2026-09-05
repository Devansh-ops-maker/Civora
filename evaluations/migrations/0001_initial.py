# Generated manually for Phase 4 - Applications.
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("challenges", "0001_initial"),
        ("startups", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Application",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "proposal",
                    models.TextField(blank=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("SUBMITTED", "Submitted"),
                            ("ELIGIBILITY_CHECK", "Eligibility Check"),
                            ("ELIGIBLE", "Eligible"),
                            ("INELIGIBLE", "Ineligible"),
                            ("UNDER_EVALUATION", "Under Evaluation"),
                            ("SELECTED", "Selected"),
                            ("REJECTED", "Rejected"),
                        ],
                        default="SUBMITTED",
                        max_length=30,
                    ),
                ),
                (
                    "eligibility_status",
                    models.BooleanField(blank=True, null=True),
                ),
                (
                    "eligibility_reason",
                    models.TextField(blank=True),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="applications",
                        to="challenges.challenge",
                    ),
                ),
                (
                    "startup",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="applications",
                        to="startups.startup",
                    ),
                ),
            ],
            options={
                "db_table": "applications",
                "ordering": ["-submitted_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="application",
            constraint=models.UniqueConstraint(
                fields=("challenge", "startup"),
                name="unique_application_per_challenge_startup",
            ),
        ),
        migrations.AddIndex(
            model_name="application",
            index=models.Index(fields=["challenge", "status"], name="evaluations_app_challeng_7d31f3_idx"),
        ),
        migrations.AddIndex(
            model_name="application",
            index=models.Index(fields=["startup", "status"], name="evaluations_app_startup_3555ea_idx"),
        ),
    ]
