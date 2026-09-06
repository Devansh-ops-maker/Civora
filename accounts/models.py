import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


class UserType(models.TextChoices):
    GOVERNMENT = "GOVERNMENT", "Government"
    STARTUP = "STARTUP", "Startup"


class UserManager(BaseUserManager):
    """
    Custom manager for the email-based User model.
    There is exactly one authentication system; role is carried on `user_type`.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if not extra_fields.get("user_type"):
            raise ValueError("user_type is required (GOVERNMENT or STARTUP)")
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # Superusers are internal/admin accounts; default them to GOVERNMENT
        # so they still satisfy the NOT NULL / role constraint.
        extra_fields.setdefault("user_type", UserType.GOVERNMENT)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Single authentication system for both Government and Startup users.
    Role-based permissions are derived from `user_type`, not from separate
    auth backends or separate models.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    user_type = models.CharField(max_length=20, choices=UserType.choices)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    LANGUAGE_CHOICES = (
        ("en", "English"),
        ("hi", "Hindi"),
    )

    preferred_language = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default="en"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "user_type"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.user_type})"

    @property
    def is_government(self):
        return self.user_type == UserType.GOVERNMENT

    @property
    def is_startup_user(self):
        return self.user_type == UserType.STARTUP


class GovernmentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="government_profile"
    )
    department_name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True)
    department_description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "government_profiles"

    def __str__(self):
        return f"{self.department_name} ({self.user.email})"


class StartupProfile(models.Model):
    """
    Lightweight profile living on accounts, separate from the richer
    `startups.Startup` (Startup Passport) model built in Phase 2.
    This mirrors the identity/account-level info; the Passport holds
    the evidence-backed capability data.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="startup_account_profile"
    )
    company_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=255, blank=True)
    technologies = models.JSONField(default=list, blank=True)
    location = models.CharField(max_length=255, blank=True)
    founded_year = models.PositiveIntegerField(null=True, blank=True)
    team_size = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "startup_account_profiles"

    def __str__(self):
        return f"{self.company_name} ({self.user.email})"
