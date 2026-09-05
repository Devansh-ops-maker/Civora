from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import GovernmentProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
from startups.models import Startup, StartupProfile, StartupEvidence, EvidenceType
from pilots.models import Pilot, PilotStatus, KPI


class TrustGraphAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="gov-graph@example.com",
            password="strongpassword123",
            name="Gov",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Water Department")

        self.startup_user = User.objects.create_user(
            email="startup-graph@example.com",
            password="strongpassword123",
            name="Startup",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup_user,
            company_name="AquaSense",
            description="Leak detection",
            industry="Water",
            technologies=["IoT"],
            team_size=8,
        )
        self.startup = Startup.objects.get(user=self.startup_user)
        StartupEvidence.objects.create(
            startup=self.startup,
            evidence_type=EvidenceType.GOVERNMENT_PILOT,
            title="Verified pilot",
            verified=True,
            verified_by=self.gov,
        )

        self.challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Leak Detection",
            problem_statement="Find leaks",
            desired_outcome="Reduce water loss",
            status=ChallengeStatus.EVALUATION,
        )
        from evaluations.models import Application, ApplicationStatus

        app = Application.objects.create(
            challenge=self.challenge,
            startup=self.startup,
            status=ApplicationStatus.SELECTED,
        )
        self.pilot = Pilot.objects.create(
            application=app,
            challenge=self.challenge,
            startup=self.startup,
            created_by=self.gov,
            title="Water Pilot",
            description="Pilot",
            status=PilotStatus.COMPLETED,
        )
        KPI.objects.create(
            pilot=self.pilot,
            name="Leak detection rate",
            description="Detection",
            unit="%",
            baseline=40,
            target=75,
            actual=80,
        )

    def test_government_can_view_startup_graph(self):
        self.client.force_authenticate(self.gov)
        response = self.client.get(f"/api/trust-graph/startups/{self.startup.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["root"]["type"], "startup")
        self.assertTrue(any(node["type"] == "pilot" for node in response.data["nodes"]))
        self.assertTrue(any(edge["relationship"] == "PARTICIPATED_IN" for edge in response.data["edges"]))

    def test_startup_can_view_own_graph(self):
        self.client.force_authenticate(self.startup_user)
        response = self.client.get(f"/api/trust-graph/startups/{self.startup.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_startup_cannot_view_other_startup_graph(self):
        other_user = User.objects.create_user(
            email="other-startup-graph@example.com",
            password="strongpassword123",
            name="Other",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=other_user,
            company_name="Other",
            description="Other",
            industry="Other",
            technologies=["Other"],
            team_size=2,
        )
        other = Startup.objects.get(user=other_user)
        self.client.force_authenticate(other_user)
        response = self.client.get(f"/api/trust-graph/startups/{self.startup.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_government_can_view_own_pilot_graph(self):
        self.client.force_authenticate(self.gov)
        response = self.client.get(f"/api/trust-graph/pilots/{self.pilot.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["root"]["type"], "pilot")
