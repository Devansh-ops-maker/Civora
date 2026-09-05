from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("pilots", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KPI",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("unit", models.CharField(max_length=100)),
                ("baseline", models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ("target", models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ("actual", models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ("direction", models.CharField(choices=[("HIGHER_IS_BETTER", "Higher is Better"), ("LOWER_IS_BETTER", "Lower is Better")], default="HIGHER_IS_BETTER", max_length=20)),
                ("status", models.CharField(choices=[("NOT_MEASURED", "Not Measured"), ("ACHIEVED", "Achieved"), ("PARTIALLY_ACHIEVED", "Partially Achieved"), ("FAILED", "Failed")], default="NOT_MEASURED", max_length=25)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pilot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="kpis", to="pilots.pilot")),
            ],
            options={"db_table": "pilot_kpis", "ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="Simulation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("assumptions", models.JSONField(blank=True, default=dict)),
                ("predicted_results", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pilot", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="simulation", to="pilots.pilot")),
            ],
            options={"db_table": "pilot_simulations"},
        ),
        migrations.CreateModel(
            name="RiskFlag",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("category", models.CharField(max_length=50)),
                ("severity", models.CharField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], max_length=20)),
                ("title", models.CharField(max_length=255)),
                ("reason", models.TextField()),
                ("mitigation", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("MITIGATED", "Mitigated"), ("ACCEPTED", "Accepted")], default="OPEN", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pilot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="risk_flags", to="pilots.pilot")),
            ],
            options={"db_table": "pilot_risk_flags", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OutcomeDecision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("recommendation", models.CharField(choices=[("SCALE", "Scale"), ("EXTEND_PILOT", "Extend Pilot"), ("STOP", "Stop")], max_length=20)),
                ("rationale", models.TextField()),
                ("kpi_summary", models.JSONField(blank=True, default=dict)),
                ("risk_summary", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("generated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outcome_decisions", to="accounts.user")),
                ("pilot", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="outcome_decision", to="pilots.pilot")),
            ],
            options={"db_table": "pilot_outcome_decisions"},
        ),
        migrations.AddIndex(model_name="kpi", index=models.Index(fields=["pilot", "status"], name="pilot_kpis_pilot_i_1a2b3c_idx")),
        migrations.AddIndex(model_name="riskflag", index=models.Index(fields=["pilot", "severity", "status"], name="pilot_risks_pilot_s_4d5e6f_idx")),
    ]
