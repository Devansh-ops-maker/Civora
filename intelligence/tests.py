from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import GovernmentProfile, StartupProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
from startups.models import Startup, StartupEvidence, EvidenceType

from .ollama import OllamaError
from .services import rank_startups


def vector(value):
    return [float(value)] + [0.0] * 1023


class RadarServiceTests(TestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="gov-radar@example.com", password="strongpassword123", name="Gov", user_type=UserType.GOVERNMENT
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Water Department")
        self.challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Municipal Leak Detection",
            problem_statement="Detect leaks in municipal water pipelines.",
            desired_outcome="Reduce water loss.",
            requirements={"required_technologies": ["IoT"], "required_industries": ["water"]},
            status=ChallengeStatus.OPEN,
            embedding=vector(1),
        )
        u1 = User.objects.create_user(
            email="a@example.com", password="strongpassword123", name="A", user_type=UserType.STARTUP
        )
        StartupProfile.objects.create(user=u1, company_name="AquaSense", description="Leak detection for municipal water", industry="Water", technologies=["IoT", "Sensors"], team_size=8)
        self.s1 = Startup.objects.get(user=u1)
        self.s1.embedding = vector(1)
        self.s1.save(update_fields=["embedding"])
        StartupEvidence.objects.create(startup=self.s1, evidence_type=EvidenceType.GOVERNMENT_PILOT, title="Municipal pilot", verified=True, verified_by=self.gov)

        u2 = User.objects.create_user(
            email="b@example.com", password="strongpassword123", name="B", user_type=UserType.STARTUP
        )
        StartupProfile.objects.create(user=u2, company_name="OtherTech", description="Generic analytics", industry="Retail", technologies=["Python"], team_size=2)
        self.s2 = Startup.objects.get(user=u2)
        self.s2.embedding = vector(0)
        self.s2.save(update_fields=["embedding"])

    def test_rank_uses_vector_search_and_deterministic_score(self):
        matches = rank_startups(self.challenge, limit=2)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["startup_id"], self.s1.id)
        self.assertEqual(matches[0]["technology_fit"], 100.0)
        self.assertEqual(matches[0]["domain_fit"], 100.0)


class RadarAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="gov-api@example.com", password="strongpassword123", name="Gov", user_type=UserType.GOVERNMENT
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Water Department")
        self.startup = User.objects.create_user(
            email="startup-api@example.com", password="strongpassword123", name="Startup", user_type=UserType.STARTUP
        )
        StartupProfile.objects.create(user=self.startup, company_name="AquaSense", description="Leak detection", industry="Water", technologies=["IoT"], team_size=8)
        self.passport = Startup.objects.get(user=self.startup)
        self.passport.embedding = vector(1)
        self.passport.save(update_fields=["embedding"])
        self.challenge = Challenge.objects.create(
            created_by=self.gov, title="Leak Detection", problem_statement="Find pipe leaks", desired_outcome="Reduce losses", requirements={"required_technologies": ["IoT"]}, status=ChallengeStatus.OPEN, embedding=vector(1)
        )

    def test_government_can_get_matches(self):
        self.client.force_authenticate(self.gov)
        response = self.client.get(f"/api/radar/challenges/{self.challenge.id}/matches/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("match_score", response.data["results"][0])

    def test_startup_cannot_get_matches(self):
        self.client.force_authenticate(self.startup)
        response = self.client.get(f"/api/radar/challenges/{self.challenge.id}/matches/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("intelligence.views.update_startup_embedding")
    def test_startup_can_refresh_own_embedding(self, mock_update):
        self.client.force_authenticate(self.startup)
        response = self.client.post("/api/radar/startups/refresh-embedding/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_update.assert_called_once_with(self.passport)

    def test_government_cannot_refresh_other_government_challenge(self):
        other = User.objects.create_user(email="othergov@example.com", password="strongpassword123", name="Other Gov", user_type=UserType.GOVERNMENT)
        self.client.force_authenticate(other)
        response = self.client.post(f"/api/radar/challenges/{self.challenge.id}/refresh-embedding/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("intelligence.services.generate_text")
    def test_explain_calls_llm_only_after_ranking(self, mock_generate):
        mock_generate.return_value = '[{"startup_id": "%s", "explanation": "Strong match.", "strengths": ["IoT"], "concerns": []}]' % self.passport.id
        self.client.force_authenticate(self.gov)
        response = self.client.post(f"/api/radar/challenges/{self.challenge.id}/explain/", {"limit": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["startup_id"], str(self.passport.id))
        mock_generate.assert_called_once()


from rest_framework import status
from rest_framework.test import APITestCase

# from accounts.models import GovernmentProfile, User, UserType
from accounts.models import GovernmentProfile, StartupProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
# from startups.models import Startup, StartupProfile, StartupEvidence, EvidenceType
from startups.models import Startup, StartupEvidence, EvidenceType
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


    def test_government_can_view_own_challenge_graph(self):
        self.client.force_authenticate(self.gov)
        response = self.client.get(f"/api/trust-graph/challenges/{self.challenge.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["root"]["type"], "challenge")
        self.assertTrue(any(edge["relationship"] == "SELECTED_STARTUP" for edge in response.data["edges"]))
