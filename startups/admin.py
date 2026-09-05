from django.contrib import admin

from .models import Startup, StartupEvidence


class StartupEvidenceInline(admin.TabularInline):
    model = StartupEvidence
    extra = 0
    fields = ["evidence_type", "title", "verified", "external_url", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Startup)
class StartupAdmin(admin.ModelAdmin):
    list_display = ["company_name", "user", "industry", "pilot_count", "deployment_count", "created_at"]
    search_fields = ["company_name", "user__email", "industry"]
    inlines = [StartupEvidenceInline]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(StartupEvidence)
class StartupEvidenceAdmin(admin.ModelAdmin):
    list_display = ["title", "startup", "evidence_type", "verified", "created_at"]
    list_filter = ["evidence_type", "verified"]
    search_fields = ["title", "startup__company_name"]
