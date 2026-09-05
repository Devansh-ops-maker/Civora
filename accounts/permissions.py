from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsGovernmentUser(BasePermission):
    """Allows access only to authenticated Government users."""

    message = "This action is restricted to government users."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_government
        )


class IsStartupUser(BasePermission):
    """Allows access only to authenticated Startup users."""

    message = "This action is restricted to startup users."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_startup_user
        )


class IsOwner(BasePermission):
    """
    Object-level permission: the object must have a `user` attribute
    (directly, or the view can override `get_owner(obj)`) that matches
    request.user. A startup must never modify another startup's data,
    and vice versa for government users.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        owner = getattr(view, "get_owner", None)
        owner_user = owner(obj) if callable(owner) else getattr(obj, "user", None)
        return owner_user == request.user


class IsOwnerOrReadOnly(BasePermission):
    """Owners can write; anyone authenticated can read (e.g. open challenges)."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(view, "get_owner", None)
        owner_user = owner(obj) if callable(owner) else getattr(obj, "user", None)
        return owner_user == request.user
