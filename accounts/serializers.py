from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers

from .models import GovernmentProfile, StartupProfile, User, UserType


class GovernmentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovernmentProfile
        fields = [
            "department_name",
            "designation",
            "department_description",
        ]


class StartupProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartupProfile
        fields = [
            "company_name",
            "description",
            "website",
            "industry",
            "technologies",
            "location",
            "founded_year",
            "team_size",
        ]


class UserSerializer(serializers.ModelSerializer):
    government_profile = GovernmentProfileSerializer(read_only=True)
    startup_account_profile = StartupProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "user_type",
            "created_at",
            "government_profile",
            "startup_account_profile",
        ]
        read_only_fields = ["id", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Single registration endpoint for both roles. The nested profile
    payload required depends on `user_type`.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    government_profile = GovernmentProfileSerializer(required=False)
    startup_account_profile = StartupProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "password",
            "user_type",
            "government_profile",
            "startup_account_profile",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        user_type = attrs.get("user_type")
        gov_data = attrs.get("government_profile")
        startup_data = attrs.get("startup_account_profile")

        if user_type == UserType.GOVERNMENT and not gov_data:
            raise serializers.ValidationError(
                {"government_profile": "Required when user_type is GOVERNMENT."}
            )
        if user_type == UserType.STARTUP and not startup_data:
            raise serializers.ValidationError(
                {"startup_account_profile": "Required when user_type is STARTUP."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        gov_data = validated_data.pop("government_profile", None)
        startup_data = validated_data.pop("startup_account_profile", None)
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        if user.user_type == UserType.GOVERNMENT and gov_data:
            GovernmentProfile.objects.create(user=user, **gov_data)
        if user.user_type == UserType.STARTUP and startup_data:
            StartupProfile.objects.create(user=user, **startup_data)

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["email"], password=attrs["password"]
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        attrs["user"] = user
        return attrs
