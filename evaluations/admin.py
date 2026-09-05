from django.contrib import admin

from .models import AIEvaluation, Application, HumanEvaluation


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("startup", "challenge", "status", "eligibility_status", "submitted_at")
    list_filter = ("status", "eligibility_status")
    search_fields = ("startup__company_name", "challenge__title", "proposal")
    readonly_fields = ("id", "submitted_at", "updated_at")


@admin.register(AIEvaluation)
class AIEvaluationAdmin(admin.ModelAdmin):
    list_display = ("application", "overall_score", "recommendation", "model_name", "created_at")
    list_filter = ("recommendation", "model_name")
    search_fields = ("application__startup__company_name", "application__challenge__title", "explanation")
    readonly_fields = ("id", "created_at")


@admin.register(HumanEvaluation)
class HumanEvaluationAdmin(admin.ModelAdmin):
    list_display = ("application", "evaluator", "overall_score", "recommendation", "created_at")
    list_filter = ("recommendation",)
    search_fields = ("application__startup__company_name", "evaluator__email", "comments")
    readonly_fields = ("id", "created_at", "updated_at")
