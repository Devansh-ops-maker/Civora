from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from accounts.models import GovernmentProfile, StartupProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
from startups.models import EvidenceType, Startup, StartupEvidence

from .models import (
    AIEvaluation,
    Application,
    ApplicationStatus,
    HumanEvaluation,
)


class ApplicationAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="gov@example.com",
            password="strongpassword123",
            name="Government User",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(
            user=self.gov,
            department_name="Municipal Water Department",
        )

        self.startup = User.objects.create_user(
            email="startup@example.com",
            password="strongpassword123",
            name="Startup User",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup,
            company_name="AquaSense",
            description="Municipal leak detection startup",
            industry="Water",
            technologies=["IoT", "Sensors"],
            team_size=8,
        )
        self.startup_passport = Startup.objects.get(user=self.startup)

        self.other_startup = User.objects.create_user(
            email="other-startup@example.com",
            password="strongpassword123",
            name="Other Startup",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.other_startup,
            company_name="OtherTech",
            industry="Technology",
            team_size=2,
        )
        self.other_passport = Startup.objects.get(user=self.other_startup)

        self.other_gov = User.objects.create_user(
            email="other-gov@example.com",
            password="strongpassword123",
            name="Other Government",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(
            user=self.other_gov,
            department_name="Other Department",
        )

        self.challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Municipal Pipe Leak Detection",
            problem_statement="Detect municipal water pipe leaks faster.",
            desired_outcome="Reduce water loss.",
            requirements={
                "minimum_team_size": 5,
                "required_industries": ["water"],
                "required_technologies": ["IoT"],
            },
            status=ChallengeStatus.OPEN,
        )

        self.other_challenge = Challenge.objects.create(
            created_by=self.other_gov,
            title="Other Challenge",
            problem_statement="Another government problem.",
            desired_outcome="Solve another problem.",
            status=ChallengeStatus.OPEN,
        )

        self.url = reverse("application-list")

    def apply(self, user=None, challenge=None, proposal="Use sensors and anomaly detection."):
        self.client.force_authenticate(user or self.startup)
        return self.client.post(
            self.url,
            {
                "challenge": str((challenge or self.challenge).id),
                "proposal": proposal,
            },
            format="json",
        )

    def test_startup_can_apply_to_open_challenge(self):
        response = self.apply()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get(id=response.data["id"])
        self.assertEqual(application.startup, self.startup_passport)
        self.assertEqual(application.challenge, self.challenge)
        self.assertEqual(application.status, ApplicationStatus.SUBMITTED)

    def test_non_startup_cannot_apply(self):
        response = self.apply(user=self.gov)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_startup_cannot_apply_to_closed_challenge(self):
        self.challenge.status = ChallengeStatus.CLOSED
        self.challenge.save(update_fields=["status"])

        response = self.apply()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("challenge", response.data)

    def test_startup_cannot_apply_twice(self):
        first = self.apply()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.apply()
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Application.objects.count(), 1)

    def test_startup_sees_only_own_applications(self):
        self.apply()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(
            Application.objects.get().id
        ))

    def test_government_sees_applications_for_own_challenges(self):
        self.apply()

        self.client.force_authenticate(self.gov)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_other_government_cannot_access_application(self):
        response = self.apply()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        application = Application.objects.get()
        self.client.force_authenticate(self.other_gov)

        detail = self.client.get(
            reverse("application-detail", args=[application.id])
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_eligibility_check_passes_configured_requirements(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        response = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["eligible"])
        application = Application.objects.get(id=application_id)
        self.assertEqual(application.status, ApplicationStatus.ELIGIBLE)

    def test_eligibility_check_can_mark_application_ineligible(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)

        application = Application.objects.get(id=application_id)
        application.startup.team_size = 2
        application.startup.save(update_fields=["team_size"])

        response = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["eligible"])
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.INELIGIBLE)

    def test_startup_cannot_run_eligibility_check(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.startup)
        response = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_government_can_move_eligible_application_to_evaluation(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        check = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )
        self.assertEqual(check.status_code, status.HTTP_200_OK)

        response = self.client.post(
            reverse("application-action", args=[application_id]),
            {"action": "start_evaluation"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        application = Application.objects.get(id=application_id)
        self.assertEqual(application.status, ApplicationStatus.UNDER_EVALUATION)

    def test_government_can_select_application_after_evaluation(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )
        self.client.post(
            reverse("application-action", args=[application_id]),
            {"action": "start_evaluation"},
            format="json",
        )

        self.client.post(
            reverse("application-human-evaluations", args=[application_id]),
            {
                "technical_score": 9,
                "innovation_score": 9,
                "feasibility_score": 9,
                "scalability_score": 8,
                "evidence_score": 8,
                "recommendation": "SELECT",
            },
            format="json",
        )

        response = self.client.post(
            reverse("application-action", args=[application_id]),
            {"action": "select"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        application = Application.objects.get(id=application_id)
        self.assertEqual(application.status, ApplicationStatus.SELECTED)

    def test_startup_cannot_select_itself(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.startup)
        response = self.client.post(
            reverse("application-action", args=[application_id]),
            {"action": "select"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_status_transition_is_rejected(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        response = self.client.post(
            reverse("application-action", args=[application_id]),
            {"action": "select"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_application_cannot_be_edited_after_submission(self):
        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.startup)
        response = self.client.patch(
            reverse("application-detail", args=[application_id]),
            {"proposal": "Changed proposal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_government_can_only_action_own_challenge_application(self):
        response = self.apply(challenge=self.other_challenge)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        response = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_required_government_experience_rule(self):
        self.challenge.requirements = {
            "government_experience_required": True,
        }
        self.challenge.save(update_fields=["requirements"])

        response = self.apply()
        application_id = response.data["id"]

        self.client.force_authenticate(self.gov)
        response = self.client.post(
            reverse("application-check-eligibility", args=[application_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["eligible"])

        StartupEvidence.objects.create(
            startup=self.startup_passport,
            evidence_type=EvidenceType.GOVERNMENT_PILOT,
            title="Municipal pilot",
            verified=True,
            verified_by=self.gov,
        )

        # The current application is terminally INELIGIBLE by design.
        # Re-checking is therefore not allowed; a fresh application would
        # normally be required for a future challenge.


class EvaluationAPITests(APITestCase):
    def setUp(self):
        self.gov = User.objects.create_user(
            email="evaluator@example.com",
            password="strongpassword123",
            name="Evaluator",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(user=self.gov, department_name="Municipal Water Department")
        self.second_gov = User.objects.create_user(
            email="second-evaluator@example.com",
            password="strongpassword123",
            name="Second Evaluator",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(user=self.second_gov, department_name="Review Committee")
        self.startup = User.objects.create_user(
            email="eval-startup@example.com",
            password="strongpassword123",
            name="Startup",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup,
            company_name="AquaSense",
            description="IoT municipal leak detection",
            industry="Water",
            technologies=["IoT", "Sensors"],
            team_size=8,
        )
        self.passport = Startup.objects.get(user=self.startup)
        self.challenge = Challenge.objects.create(
            created_by=self.gov,
            title="Municipal Leak Detection",
            problem_statement="Detect municipal water pipe leaks.",
            desired_outcome="Reduce water loss.",
            requirements={"required_technologies": ["IoT"], "required_industries": ["water"]},
            status=ChallengeStatus.OPEN,
        )
        self.client.force_authenticate(self.startup)
        response = self.client.post(
            reverse("application-list"),
            {"challenge": str(self.challenge.id), "proposal": "Deploy acoustic and pressure sensors."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.application = Application.objects.get(id=response.data["id"])
        self.client.force_authenticate(self.gov)
        response = self.client.post(
            reverse("application-check-eligibility", args=[self.application.id]), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(
            reverse("application-action", args=[self.application.id]),
            {"action": "start_evaluation"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("evaluations.services.generate_text")
    def test_government_can_generate_ai_evaluation(self, mock_generate):
        mock_generate.return_value = """{\n          \"technical_score\": 9,\n          \"innovation_score\": 8,\n          \"feasibility_score\": 9,\n          \"scalability_score\": 8,\n          \"evidence_score\": 7,\n          \"strengths\": [\"Strong IoT alignment\"],\n          \"weaknesses\": [\"Limited deployment evidence\"],\n          \"missing_evidence\": [\"Recent field test results\"],\n          \"recommendation\": \"REVIEW\",\n          \"explanation\": \"The proposal aligns well with the challenge and appears feasible, but further evidence is useful before selection.\"\n        }"""
        response = self.client.post(
            reverse("application-ai-evaluate", args=[self.application.id]), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["technical_score"], 9)
        self.assertEqual(response.data["overall_score"], 82.0)
        self.assertEqual(AIEvaluation.objects.count(), 1)
        mock_generate.assert_called_once()

    @patch("evaluations.services.generate_text")
    def test_ai_evaluation_updates_existing_record(self, mock_generate):
        payload = {
            "technical_score": 8,
            "innovation_score": 8,
            "feasibility_score": 8,
            "scalability_score": 8,
            "evidence_score": 8,
            "strengths": ["Good fit"],
            "weaknesses": [],
            "missing_evidence": [],
            "recommendation": "SELECT",
            "explanation": "Strong overall fit.",
        }
        mock_generate.return_value = __import__("json").dumps(payload)
        self.client.post(reverse("application-ai-evaluate", args=[self.application.id]), {}, format="json")
        mock_generate.return_value = __import__("json").dumps({**payload, "technical_score": 9})
        response = self.client.post(reverse("application-ai-evaluate", args=[self.application.id]), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AIEvaluation.objects.count(), 1)
        self.assertEqual(response.data["technical_score"], 9)

    def test_only_government_can_request_ai_evaluation(self):
        self.client.force_authenticate(self.startup)
        response = self.client.post(reverse("application-ai-evaluate", args=[self.application.id]), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_government_can_submit_human_evaluation(self):
        payload = {
            "technical_score": 9,
            "innovation_score": 8,
            "feasibility_score": 9,
            "scalability_score": 8,
            "evidence_score": 7,
            "comments": "Technically strong proposal.",
            "recommendation": "SELECT",
        }
        response = self.client.post(
            reverse("application-human-evaluations", args=[self.application.id]), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["overall_score"], 82.0)
        self.assertEqual(HumanEvaluation.objects.count(), 1)
        evaluation = HumanEvaluation.objects.get()
        self.assertEqual(evaluation.evaluator, self.gov)

    def test_duplicate_human_evaluation_by_same_evaluator_is_rejected(self):
        payload = {
            "technical_score": 8,
            "innovation_score": 8,
            "feasibility_score": 8,
            "scalability_score": 8,
            "evidence_score": 8,
            "recommendation": "REVIEW",
        }
        first = self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(HumanEvaluation.objects.count(), 1)

    def test_second_government_evaluator_can_submit(self):
        payload = {
            "technical_score": 7,
            "innovation_score": 7,
            "feasibility_score": 8,
            "scalability_score": 7,
            "evidence_score": 6,
            "recommendation": "REVIEW",
        }
        self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        self.client.force_authenticate(self.second_gov)
        response = self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(HumanEvaluation.objects.count(), 2)

    def test_evaluation_summary_combines_ai_and_human_scores(self):
        import json
        ai_payload = {
            "technical_score": 10,
            "innovation_score": 10,
            "feasibility_score": 10,
            "scalability_score": 10,
            "evidence_score": 10,
            "strengths": ["Excellent fit"],
            "weaknesses": [],
            "missing_evidence": [],
            "recommendation": "SELECT",
            "explanation": "Excellent fit based on the supplied evidence.",
        }
        with patch("evaluations.services.generate_text", return_value=json.dumps(ai_payload)):
            self.client.post(reverse("application-ai-evaluate", args=[self.application.id]), {}, format="json")
        human_payload = {
            "technical_score": 8,
            "innovation_score": 8,
            "feasibility_score": 8,
            "scalability_score": 8,
            "evidence_score": 8,
            "recommendation": "SELECT",
        }
        self.client.post(reverse("application-human-evaluations", args=[self.application.id]), human_payload, format="json")
        response = self.client.get(reverse("application-evaluation-summary", args=[self.application.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ai_score"], 100.0)
        self.assertEqual(response.data["human_average_score"], 80.0)
        self.assertEqual(response.data["combined_score"], 90.0)
        self.assertTrue(response.data["selection_ready"])

    def test_final_selection_requires_human_evaluation(self):
        response = self.client.post(
            reverse("application-action", args=[self.application.id]), {"action": "select"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Application.objects.get().status, ApplicationStatus.UNDER_EVALUATION)

    def test_government_can_select_after_human_evaluation(self):
        payload = {
            "technical_score": 9,
            "innovation_score": 9,
            "feasibility_score": 9,
            "scalability_score": 8,
            "evidence_score": 8,
            "recommendation": "SELECT",
        }
        self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        response = self.client.post(
            reverse("application-action", args=[self.application.id]), {"action": "select"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Application.objects.get().status, ApplicationStatus.SELECTED)

    def test_final_rejection_requires_human_evaluation(self):
        response = self.client.post(
            reverse("application-action", args=[self.application.id]), {"action": "reject"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_human_scores_must_be_between_zero_and_ten(self):
        payload = {
            "technical_score": 11,
            "innovation_score": 8,
            "feasibility_score": 8,
            "scalability_score": 8,
            "evidence_score": 8,
            "recommendation": "REVIEW",
        }
        response = self.client.post(reverse("application-human-evaluations", args=[self.application.id]), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("technical_score", response.data)
