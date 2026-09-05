from django.contrib import admin

from .models import Challenge


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created_by",
        "status",
        "budget",
        "application_deadline",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("title", "problem_statement", "desired_outcome")
    readonly_fields = ("id", "created_at", "updated_at")
