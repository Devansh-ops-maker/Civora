# Generated manually to keep the uploaded project self-contained.

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Challenge",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "title",
                    models.CharField(max_length=255),
                ),
                (
                    "problem_statement",
                    models.TextField(),
                ),
                (
                    "desired_outcome",
                    models.TextField(),
                ),
                (
                    "requirements",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "constraints",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "budget",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
                ),
                (
                    "start_date",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "application_deadline",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("OPEN", "Open"),
                            ("EVALUATION", "Evaluation"),
                            ("PILOT", "Pilot"),
                            ("COMPLETED", "Completed"),
                            ("CLOSED", "Closed"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "challenges",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["created_by", "status"], name="challenges_created_b9c7c7_idx"),
                    models.Index(fields=["status", "application_deadline"], name="challenges_status_0e9d22_idx"),
                ],
            },
        ),
    ]
