
from .models import KPI, KPIDirection, KPIStatus, OutcomeDecision, OutcomeRecommendation, Pilot, PilotStatus
from evaluations.models import Application, ApplicationStatus
from startups.models import Startup
from challenges.models import Challenge, ChallengeStatus
from accounts.models import User, UserType
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import GovernmentProfile, StartupProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
from evaluations.models import Application, ApplicationStatus, HumanEvaluation
from startups.models import Startup

from .models import Milestone, MilestoneStatus, Payment, Pilot, PilotStatus


class PilotAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="pilotgov@example.com",
            password="strongpassword123",
            name="Government",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Water Department")
        self.startup_user = User.objects.create_user(
            email="pilotstartup@example.com",
            password="strongpassword123",
            name="Startup",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup_user,
            company_name="AquaSense",
            description="Water leak detection",
            industry="Water",
            technologies=["IoT"],
            team_size=10,
        )
        self.startup = Startup.objects.get(user=self.startup_user)
        self.challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Leak Detection",
            problem_statement="Detect municipal water leaks.",
            desired_outcome="Reduce water loss.",
            status=ChallengeStatus.OPEN,
        )
        self.application = Application.objects.create(
            challenge=self.challenge,
            startup=self.startup,
            proposal="Detect leaks with IoT sensors.",
            status=ApplicationStatus.SELECTED,
        )
        HumanEvaluation.objects.create(
            application=self.application,
            evaluator=self.gov,
            technical_score=9,
            innovation_score=8,
            feasibility_score=9,
            scalability_score=8,
            evidence_score=8,
            recommendation="SELECT",
        )

    def test_only_selected_application_can_create_pilot(self):
        self.client.force_authenticate(self.gov)
        response = self.client.post(
            "/api/pilots/",
            {
                "application": str(self.application.id),
                "title": "Leak Detection Pilot",
                "description": "Pilot the startup solution.",
                "objectives": ["Reduce detection time"],
                "budget": "100000.00",
                "start_date": "2026-09-05",
                "end_date": "2026-12-04",
                "success_criteria": ["Detection time reduced by 30%"],
                "data_requirements": ["Pressure readings"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pilot.objects.count(), 1)

    def test_startup_cannot_create_pilot(self):
        self.client.force_authenticate(self.startup_user)
        response = self.client.post(
            "/api/pilots/",
            {"application": str(self.application.id), "title": "Nope", "description": "Nope"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_startup_can_read_own_pilot(self):
        pilot = Pilot.objects.create(
            application=self.application,
            challenge=self.challenge,
            startup=self.startup,
            created_by=self.gov,
            title="Pilot",
            description="Pilot description",
        )
        self.client.force_authenticate(self.startup_user)
        response = self.client.get(f"/api/pilots/{pilot.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pilot_status_actions(self):
        pilot = Pilot.objects.create(
            application=self.application,
            challenge=self.challenge,
            startup=self.startup,
            created_by=self.gov,
            title="Pilot",
            description="Pilot description",
        )
        self.client.force_authenticate(self.gov)
        response = self.client.post(f"/api/pilots/{pilot.id}/action/", {"action": "activate"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PilotStatus.ACTIVE)


class MilestoneAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="milestonegov@example.com",
            password="strongpassword123",
            name="Government",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Water Department")
        self.startup_user = User.objects.create_user(
            email="milestonestartup@example.com",
            password="strongpassword123",
            name="Startup",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup_user,
            company_name="AquaSense",
            description="Water leak detection",
            industry="Water",
            technologies=["IoT"],
            team_size=10,
        )
        self.startup = Startup.objects.get(user=self.startup_user)
        challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Leak Detection",
            problem_statement="Detect municipal water leaks.",
            desired_outcome="Reduce water loss.",
            status=ChallengeStatus.OPEN,
        )
        application = Application.objects.create(
            challenge=challenge,
            startup=self.startup,
            proposal="Pilot",
            status=ApplicationStatus.SELECTED,
        )
        self.pilot = Pilot.objects.create(
            application=application,
            challenge=challenge,
            startup=self.startup,
            created_by=self.gov,
            title="Leak Pilot",
            description="Pilot",
            status=PilotStatus.ACTIVE,
        )
        self.milestone = Milestone.objects.create(
            pilot=self.pilot,
            title="Deploy",
            description="Deploy sensors",
            amount="200000.00",
        )

    def test_startup_can_submit_milestone(self):
        self.client.force_authenticate(self.startup_user)
        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/submit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, MilestoneStatus.SUBMITTED)

    def test_government_can_review_verify_approve_and_pay(self):
        self.client.force_authenticate(self.startup_user)
        self.client.post(f"/api/pilots/milestones/{self.milestone.id}/submit/")

        # A government user cannot submit startup evidence.
        self.client.force_authenticate(self.gov)
        response = self.client.post(
            f"/api/pilots/{self.pilot.id}/evidence/",
            {"milestone": str(self.milestone.id), "evidence_type": "TEST_RESULT", "title": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Startup submits evidence before government review.
        self.client.force_authenticate(self.startup_user)
        response = self.client.post(
            f"/api/pilots/{self.pilot.id}/evidence/",
            {"milestone": str(self.milestone.id), "evidence_type": "TEST_RESULT", "title": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        evidence_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/review/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/verify/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            f"/api/pilots/evidence-records/{evidence_id}/verify/",
            {"verified": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/verify/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/approve-payment/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(f"/api/pilots/milestones/{self.milestone.id}/pay/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, MilestoneStatus.PAID)
        self.assertTrue(Payment.objects.filter(milestone=self.milestone, status=MilestoneStatus.PAID).exists())

    @patch("pilots.views.generate_pilot_plan")
    def test_generate_plan_endpoint(self, mock_generate):
        self.client.force_authenticate(self.gov)
        mock_generate.return_value = {
            "title": "Generated Pilot",
            "description": "Generated",
            "objectives": ["Test"],
            "budget": 100000,
            "duration_days": 30,
            "success_criteria": ["Pass"],
            "data_requirements": ["Telemetry"],
            "milestones": [],
        }
        response = self.client.post(f"/api/pilots/{self.pilot.id}/generate-plan/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_generate.assert_called_once_with(self.pilot.application)


class OutcomeAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(email="outcomes-gov@example.com", password="pass", user_type=UserType.GOVERNMENT)
        self.startup_user = User.objects.create_user(email="outcomes-startup@example.com", password="pass", user_type=UserType.STARTUP)
        self.startup = Startup.objects.create(user=self.startup_user, company_name="Outcome Startup", description="IoT", industry="water", technologies=["IoT"])
        self.challenge = Challenge.objects.create(created_by=self.gov, title="Water", problem_statement="Leaks", desired_outcome="Reduce losses", status=ChallengeStatus.PILOT, budget=10000)
        self.app = Application.objects.create(challenge=self.challenge, startup=self.startup, status=ApplicationStatus.SELECTED)
        self.pilot = Pilot.objects.create(application=self.app, challenge=self.challenge, startup=self.startup, created_by=self.gov, title="Pilot", description="Test", status=PilotStatus.COMPLETED)
        self.client.force_authenticate(self.gov)

    def test_kpi_evaluates_lower_is_better(self):
        kpi = KPI.objects.create(pilot=self.pilot, name="Response time", unit="hours", baseline=10, target=5, actual=5, direction=KPIDirection.LOWER_IS_BETTER)
        self.assertEqual(kpi.status, KPIStatus.ACHIEVED)

    def test_generate_simulation(self):
        KPI.objects.create(pilot=self.pilot, name="Detection", unit="%", baseline=40, target=80, direction=KPIDirection.HIGHER_IS_BETTER)
        response = self.client.post(f"/api/pilots/{self.pilot.id}/simulate/", {"assumptions": {"expected_progress": 0.5}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pilot"], str(self.pilot.id))

    def test_risk_check_and_outcome(self):
        KPI.objects.create(pilot=self.pilot, name="Detection", unit="%", baseline=40, target=80, actual=90)
        response = self.client.post(f"/api/pilots/{self.pilot.id}/risk-check/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(f"/api/pilots/{self.pilot.id}/outcome/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["recommendation"], "SCALE")

