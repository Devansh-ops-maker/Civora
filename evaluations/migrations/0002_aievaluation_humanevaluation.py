from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("evaluations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIEvaluation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("technical_score", models.PositiveSmallIntegerField()),
                ("innovation_score", models.PositiveSmallIntegerField()),
                ("feasibility_score", models.PositiveSmallIntegerField()),
                ("scalability_score", models.PositiveSmallIntegerField()),
                ("evidence_score", models.PositiveSmallIntegerField()),
                ("strengths", models.JSONField(blank=True, default=list)),
                ("weaknesses", models.JSONField(blank=True, default=list)),
                ("missing_evidence", models.JSONField(blank=True, default=list)),
                ("recommendation", models.CharField(choices=[("SELECT", "Select"), ("REJECT", "Reject"), ("REVIEW", "Further Review")], default="REVIEW", max_length=10)),
                ("explanation", models.TextField()),
                ("model_name", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ai_evaluation", to="evaluations.application")),
            ],
            options={
                "db_table": "ai_evaluations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="HumanEvaluation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("technical_score", models.PositiveSmallIntegerField()),
                ("innovation_score", models.PositiveSmallIntegerField()),
                ("feasibility_score", models.PositiveSmallIntegerField()),
                ("scalability_score", models.PositiveSmallIntegerField()),
                ("evidence_score", models.PositiveSmallIntegerField()),
                ("comments", models.TextField(blank=True)),
                ("recommendation", models.CharField(choices=[("SELECT", "Select"), ("REJECT", "Reject"), ("REVIEW", "Further Review")], default="REVIEW", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="human_evaluations", to="evaluations.application")),
                ("evaluator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="human_evaluations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "human_evaluations",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["application", "created_at"], name="human_eval_application_created_idx"),
                    models.Index(fields=["evaluator", "created_at"], name="human_eval_evaluator_created_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["application", "evaluator"], name="unique_human_evaluation_per_evaluator"),
                ],
            },
        ),
    ]
