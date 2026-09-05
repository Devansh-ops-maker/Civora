# Generated manually for Phase 7 pilot workflow.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("challenges", "0003_rename_challenges_created_b9c7c7_idx_challenges_created_739886_idx_and_more"),
        ("evaluations", "0003_rename_evaluations_app_challeng_7d31f3_idx_application_challen_7170a3_idx_and_more"),
        ("startups", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Pilot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("objectives", models.JSONField(blank=True, default=list)),
                ("budget", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("success_criteria", models.JSONField(blank=True, default=list)),
                ("data_requirements", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("ACTIVE", "Active"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="DRAFT", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("application", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="pilot", to="evaluations.application")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pilots", to="challenges.challenge")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_pilots", to=settings.AUTH_USER_MODEL)),
                ("startup", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pilots", to="startups.startup")),
            ],
            options={
                "db_table": "pilots",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["created_by", "status"], name="pilots_created_bf2e6b_idx"),
                    models.Index(fields=["startup", "status"], name="pilots_startup_9c51cc_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Milestone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=15)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SUBMITTED", "Submitted"), ("UNDER_REVIEW", "Under Review"), ("VERIFIED", "Verified"), ("PAYMENT_APPROVED", "Payment Approved"), ("PAID", "Paid")], default="PENDING", max_length=30)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("payment_approved_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pilot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="milestones", to="pilots.pilot")),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="verified_pilot_milestones", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "pilot_milestones",
                "ordering": ["due_date", "created_at"],
                "indexes": [
                    models.Index(fields=["pilot", "status"], name="pilot_miles_pilot_s_2b7d91_idx"),
                    models.Index(fields=["due_date", "status"], name="pilot_miles_due_dat_48fbb2_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PilotEvidence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("evidence_type", models.CharField(choices=[("DEPLOYMENT_REPORT", "Deployment Report"), ("TEST_RESULT", "Test Result"), ("KPI_REPORT", "KPI Report"), ("GOVERNMENT_REPORT", "Government Report"), ("SYSTEM_LOG", "System Log"), ("PHOTO", "Photo"), ("OTHER", "Other")], max_length=30)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("file", models.FileField(blank=True, null=True, upload_to="pilot_evidence/")),
                ("external_url", models.URLField(blank=True)),
                ("verified", models.BooleanField(default=False)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("milestone", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence", to="pilots.milestone")),
                ("pilot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence", to="pilots.pilot")),
                ("submitted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submitted_pilot_evidence", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="verified_pilot_evidence", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "pilot_evidence",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["pilot", "milestone"], name="pilot_ev_pilot_m_4f5dd1_idx"),
                    models.Index(fields=["verified", "created_at"], name="pilot_ev_verified_3a4dd6_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=15)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("PAID", "Paid")], default="PENDING", max_length=20)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("milestone", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payment", to="pilots.milestone")),
            ],
            options={
                "db_table": "pilot_payments",
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["status", "created_at"], name="pilot_paym_status_7ee9ea_idx")],
            },
        ),
    ]
