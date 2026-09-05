from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserType
from .models import Challenge, ChallengeStatus


class ChallengeAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="gov@example.com",
            password="strongpassword123",
            name="Government User",
            user_type=UserType.GOVERNMENT,
        )
        self.startup = User.objects.create_user(
            email="startup@example.com",
            password="strongpassword123",
            name="Startup User",
            user_type=UserType.STARTUP,
        )
        self.url = reverse("challenge-list")

    def challenge_payload(self):
        return {
            "title": "Municipal Pipe Leak Detection",
            "problem_statement": "Detect municipal water pipe leaks faster.",
            "desired_outcome": "Reduce leak detection time and water loss.",
            "requirements": ["IoT sensors", "Real-time alerts"],
            "constraints": ["Must support municipal infrastructure"],
            "budget": "500000.00",
            "start_date": "2026-10-01",
            "application_deadline": "2026-09-25",
        }

    def test_government_can_create_challenge(self):
        self.client.force_authenticate(self.gov)
        response = self.client.post(self.url, self.challenge_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        challenge = Challenge.objects.get(id=response.data["id"])
        self.assertEqual(challenge.created_by, self.gov)
        self.assertEqual(challenge.status, ChallengeStatus.DRAFT)

    def test_startup_cannot_create_challenge(self):
        self.client.force_authenticate(self.startup)
        response = self.client.post(self.url, self.challenge_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_startup_can_read_open_challenge(self):
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Test Challenge",
            problem_statement="Test problem",
            desired_outcome="Test outcome",
            status=ChallengeStatus.OPEN,
        )

        self.client.force_authenticate(self.startup)

        response = self.client.get(
            reverse("challenge-detail", args=[challenge.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(challenge.id))

    def test_only_owner_government_can_modify_challenge(self):
        other_gov = User.objects.create_user(
            email="othergov@example.com",
            password="strongpassword123",
            name="Other Government",
            user_type=UserType.GOVERNMENT,
        )
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Test Challenge",
            problem_statement="Test problem",
            desired_outcome="Test outcome",
        )

        self.client.force_authenticate(other_gov)
        response = self.client.patch(
            reverse("challenge-detail", args=[challenge.id]),
            {"title": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_status_jump_is_rejected(self):
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Test Challenge",
            problem_statement="Test problem",
            desired_outcome="Test outcome",
        )
        self.client.force_authenticate(self.gov)

        response = self.client.post(
            reverse("challenge-transition", args=[challenge.id]),
            {"status": ChallengeStatus.COMPLETED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, ChallengeStatus.DRAFT)

    def test_valid_status_transition(self):
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Test Challenge",
            problem_statement="Test problem",
            desired_outcome="Test outcome",
        )
        self.client.force_authenticate(self.gov)

        response = self.client.post(
            reverse("challenge-transition", args=[challenge.id]),
            {"status": ChallengeStatus.OPEN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, ChallengeStatus.OPEN)

    def test_invalid_dates_are_rejected(self):
        self.client.force_authenticate(self.gov)
        payload = self.challenge_payload()
        payload["application_deadline"] = "2026-10-02"
        payload["start_date"] = "2026-10-01"

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("application_deadline", response.data)
    def test_startup_cannot_read_draft_challenge(self):
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Private Challenge",
            problem_statement="Private problem",
            desired_outcome="Private outcome",
            status=ChallengeStatus.DRAFT,
        )

        self.client.force_authenticate(self.startup)

        response = self.client.get(
            reverse("challenge-detail", args=[challenge.id])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)