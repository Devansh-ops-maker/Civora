from rest_framework.permissions import BasePermission

from accounts.models import UserType


class PilotPermission(BasePermission):
    message = "You do not have permission to access this pilot."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.user_type in {
            UserType.GOVERNMENT,
            UserType.STARTUP,
        })

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.user_type == UserType.STARTUP:
            return obj.startup.user_id == user.id
        if user.user_type == UserType.GOVERNMENT:
            return obj.created_by_id == user.id
        return False


class MilestonePermission(BasePermission):
    message = "You do not have permission to access this milestone."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.user_type in {
            UserType.GOVERNMENT,
            UserType.STARTUP,
        })

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.user_type == UserType.STARTUP:
            return obj.pilot.startup.user_id == user.id
        if user.user_type == UserType.GOVERNMENT:
            return obj.pilot.created_by_id == user.id
        return False


class PilotEvidencePermission(BasePermission):
    message = "You do not have permission to access this pilot evidence."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.user_type in {
            UserType.GOVERNMENT,
            UserType.STARTUP,
        })

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.user_type == UserType.STARTUP:
            return obj.pilot.startup.user_id == user.id
        if user.user_type == UserType.GOVERNMENT:
            return obj.pilot.created_by_id == user.id
        return False
