from rest_framework.permissions import BasePermission

from accounts.models import UserType

class ApplicationPermission(BasePermission):
    """
    Startup users can create and view their own applications.

    Government users:
    - Any government user can perform evaluation-related actions.
    - Only the government user that created the challenge can
      perform eligibility, selection, and rejection actions.
    """

    message = "You do not have permission to access this application."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(view, "action", None) == "create":
            return user.user_type == UserType.STARTUP

        return user.user_type in {
            UserType.STARTUP,
            UserType.GOVERNMENT,
        }

    def has_object_permission(self, request, view, obj):
        user = request.user
        action = getattr(view, "action", None)

        if user.user_type == UserType.STARTUP:
            return obj.startup.user_id == user.id

        if user.user_type == UserType.GOVERNMENT:

            # Any government evaluator can evaluate.
            if action in [
                "ai_evaluate",
                "human_evaluations",
                "evaluation_summary",
            ]:
                return True

            # Challenge owner controls the application workflow.
            return obj.challenge.created_by_id == user.id

        return False