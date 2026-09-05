from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import GovernmentProfile, StartupProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "name", "user_type", "is_staff", "is_active", "created_at"]
    list_filter = ["user_type", "is_staff", "is_active"]
    search_fields = ["email", "name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "user_type")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "user_type", "password1", "password2"),
            },
        ),
    )


@admin.register(GovernmentProfile)
class GovernmentProfileAdmin(admin.ModelAdmin):
    list_display = ["department_name", "user", "designation"]
    search_fields = ["department_name", "user__email"]


@admin.register(StartupProfile)
class StartupProfileAdmin(admin.ModelAdmin):
    list_display = ["company_name", "user", "industry"]
    search_fields = ["company_name", "user__email"]
