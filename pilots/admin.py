from django.contrib import admin

from .models import Milestone, Payment, Pilot, PilotEvidence


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = ("title", "startup", "status", "budget", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("title", "startup__company_name")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("title", "pilot", "amount", "status", "due_date")
    list_filter = ("status",)


@admin.register(PilotEvidence)
class PilotEvidenceAdmin(admin.ModelAdmin):
    list_display = ("title", "pilot", "milestone", "verified", "created_at")
    list_filter = ("verified", "evidence_type")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("milestone", "amount", "status", "reference", "paid_at")
    list_filter = ("status",)

from .models import KPI, OutcomeDecision, RiskFlag, Simulation

admin.site.register(KPI)
admin.site.register(Simulation)
admin.site.register(RiskFlag)
admin.site.register(OutcomeDecision)
