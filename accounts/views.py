from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import GovernmentProfile, StartupProfile, UserType
from .serializers import (
    GovernmentProfileSerializer,
    LoginSerializer,
    RegisterSerializer,
    StartupProfileSerializer,
    UserSerializer,
)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Single registration endpoint for both GOVERNMENT and STARTUP users.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": _tokens_for_user(user),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login/"""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": _tokens_for_user(user),
            }
        )


class MeView(APIView):
    """GET/PATCH /api/auth/me/ - the current authenticated user + profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        name = request.data.get("name")
        if name:
            user.name = name
            user.save(update_fields=["name"])

        profile_data = request.data.get("profile")
        if profile_data and user.user_type == UserType.GOVERNMENT:
            profile, _ = GovernmentProfile.objects.get_or_create(user=user)
            serializer = GovernmentProfileSerializer(
                profile, data=profile_data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        elif profile_data and user.user_type == UserType.STARTUP:
            profile, _ = StartupProfile.objects.get_or_create(user=user)
            serializer = StartupProfileSerializer(
                profile, data=profile_data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(UserSerializer(user).data)
