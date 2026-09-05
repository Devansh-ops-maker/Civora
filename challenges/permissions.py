from rest_framework.permissions import BasePermission, SAFE_METHODS


class ChallengePermission(BasePermission):
    """
    Authenticated users may read challenges.
    Only government users may create challenges.
    Only the government user that created a challenge may update/delete it.
    """

    message = "Only government users can create or modify challenges."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return user.is_government

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user == obj.created_by and request.user.is_government
