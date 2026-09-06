import json
import os
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import GovernmentProfile, StartupProfile, User, UserType
from challenges.models import Challenge, ChallengeStatus
from startups.models import Startup, StartupEvidence, EvidenceType

from .ollama import OllamaError
from .scrapers import StartupIndiaScraper, get_startup_schemes, get_startup_schemes_json
from .scrapers.startup_india import _clean_list, _clean_text, _first, _normalize_scheme
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


SAMPLE_RAW_API_DATA = {
    "status": "success",
    "message": "OK",
    "data": {
        "searchResult": {
            "Ministry of Agriculture": [
                {
                    "id": "agri-101",
                    "schname": ["Agri-Tech Infrastructure Scheme"],
                    "mname": ["Ministry of Agriculture"],
                    "title": ["Ministry of Agriculture"],
                    "brief": ["<p>Funding for <b>smart farming</b> equipment.</p>"],
                    "benefits": ["Financial grant up to 25 Lakhs", "Free mentorship"],
                    "benefitTags": ["Grant", "Mentorship"],
                    "EligibilityCriteria": ["DPIIT recognised startups", "Agriculture sector"],
                    "quantumSize": ["Up to 25 Lakhs"],
                    "sector": ["Agriculture", "Agri-Tech"],
                    "tenure": ["Active"],
                    "notes": ["Apply before financial year end."],
                    "linktoApplication": ["https://agri.gov.in/scheme101"],
                }
            ],
            "Ministry of Electronics and IT": [
                {
                    "id": "meity-202",
                    "schname": ["Digital India Innovation Fund"],
                    "mname": None,
                    "title": ["MeitY Initiatives"],
                    "brief": ["Support for deep-tech and AI innovations."],
                    "benefits": ["Equity investment"],
                    "benefitTags": ["Investment"],
                    "EligibilityCriteria": ["Tech startups"],
                    "quantumSize": ["Up to 1 Crore"],
                    "sector": ["Artificial Intelligence", "SaaS"],
                    "tenure": ["Active"],
                    "notes": None,
                    "linktoApplication": ["https://meity.gov.in/diif"],
                }
            ],
        }
    },
}


class StartupIndiaScraperTests(TestCase):
    def test_clean_text(self):
        self.assertIsNone(_clean_text(None))
        self.assertIsNone(_clean_text("   "))
        self.assertEqual(
            _clean_text("<p>Hello   <b>World</b>\n</p>"),
            "Hello World",
        )

    def test_clean_list(self):
        self.assertEqual(_clean_list(None), [])
        self.assertEqual(_clean_list("null"), [])
        self.assertEqual(_clean_list("undefined"), [])
        self.assertEqual(_clean_list("single item"), ["single item"])
        self.assertEqual(
            _clean_list(["  Item 1  ", None, "<p>Item 2</p>", "   "]),
            ["Item 1", "Item 2"],
        )

    def test_first(self):
        self.assertIsNone(_first(None))
        self.assertIsNone(_first([]))
        self.assertEqual(_first(["First", "Second"]), "First")
        self.assertEqual(_first("Direct String"), "Direct String")

    def test_normalize_scheme(self):
        raw = {
            "id": "test-id",
            "schname": ["<b>Test Scheme</b>"],
            "mname": None,
            "title": ["Parent Ministry"],
            "brief": ["<p>Scheme brief description.</p>"],
            "benefits": ["Benefit 1", "Benefit 2"],
            "benefitTags": ["Financial"],
            "EligibilityCriteria": ["Seed stage"],
            "quantumSize": ["10L"],
            "sector": ["FinTech"],
            "tenure": ["Active"],
            "notes": ["Important note"],
            "linktoApplication": ["https://apply.gov.in"],
        }
        normalized = _normalize_scheme(raw, "Fallback Ministry")
        self.assertEqual(normalized["id"], "test-id")
        self.assertEqual(normalized["scheme_name"], "Test Scheme")
        self.assertEqual(normalized["ministry"], "Parent Ministry")
        self.assertEqual(normalized["source_group"], "Fallback Ministry")
        self.assertEqual(normalized["brief"], "Scheme brief description.")
        self.assertEqual(normalized["benefits"], ["Benefit 1", "Benefit 2"])
        self.assertEqual(normalized["benefit_tags"], ["Financial"])
        self.assertEqual(normalized["eligibility_criteria"], ["Seed stage"])
        self.assertEqual(normalized["application_url"], "https://apply.gov.in")

    def test_parse_schemes(self):
        scraper = StartupIndiaScraper()
        result = scraper.parse_schemes(SAMPLE_RAW_API_DATA)
        self.assertIn("metadata", result)
        self.assertIn("schemes", result)
        self.assertEqual(result["metadata"]["scheme_count"], 2)
        self.assertEqual(result["metadata"]["group_count"], 2)
        schemes = result["schemes"]
        self.assertEqual(len(schemes), 2)
        # Verify alphabetical sorting by ministry ("meity" < "ministry")
        self.assertEqual(schemes[0]["ministry"], "MeitY Initiatives")
        self.assertEqual(schemes[1]["ministry"], "Ministry of Agriculture")

    @patch("requests.get")
    def test_get_startup_schemes_mocked(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_RAW_API_DATA
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        data = get_startup_schemes(timeout=15)
        self.assertEqual(data["metadata"]["scheme_count"], 2)
        self.assertEqual(len(data["schemes"]), 2)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["timeout"], 15)

    @patch("requests.get")
    def test_get_startup_schemes_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_RAW_API_DATA
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        json_str = get_startup_schemes_json()
        parsed = json.loads(json_str)
        self.assertIn("schemes", parsed)
        self.assertEqual(len(parsed["schemes"]), 2)


class ScrapeStartupSchemesCommandTests(TestCase):
    @patch("intelligence.management.commands.scrape_startup_schemes.get_startup_schemes")
    def test_command_stdout(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 1, "group_count": 1},
            "schemes": [
                {"scheme_name": "Standup Scheme", "ministry": "Finance"}
            ],
        }
        out = StringIO()
        call_command("scrape_startup_schemes", stdout=out)
        output = out.getvalue()
        self.assertIn("Standup Scheme", output)
        self.assertIn("Finance", output)

    @patch("intelligence.management.commands.scrape_startup_schemes.get_startup_schemes")
    def test_command_file_output(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 1, "group_count": 1},
            "schemes": [
                {"scheme_name": "File Test Scheme", "ministry": "IT"}
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "schemes.json")
            out = StringIO()
            call_command("scrape_startup_schemes", output=file_path, stdout=out)
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(len(saved["schemes"]), 1)
            self.assertEqual(saved["schemes"][0]["scheme_name"], "File Test Scheme")
            self.assertIn("Successfully scraped 1 schemes", out.getvalue())

    @patch("intelligence.management.commands.scrape_startup_schemes.get_startup_schemes")
    def test_command_request_error(self, mock_scrape):
        mock_scrape.side_effect = requests.RequestException("Network unreachable")
        with self.assertRaises(CommandError) as ctx:
            call_command("scrape_startup_schemes")
        self.assertIn("Failed to scrape Startup India schemes", str(ctx.exception))


class RadarSchemesAPITests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.startup_user = User.objects.create_user(
            email="startup-radar-schemes@example.com",
            password="strongpassword123",
            name="Startup User",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup_user,
            company_name="SchemeStartup",
            description="Testing schemes",
            industry="Tech",
            technologies=["Python"],
            team_size=5,
        )
        self.gov_user = User.objects.create_user(
            email="gov-radar-schemes@example.com",
            password="strongpassword123",
            name="Gov User",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(
            user=self.gov_user,
            department_name="Department of Commerce",
        )

    def test_unauthenticated_schemes_denied(self):
        response = self.client.get("/api/radar/schemes/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_government_user_forbidden(self):
        self.client.force_authenticate(self.gov_user)
        response = self.client.get("/api/radar/schemes/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("intelligence.views.get_startup_schemes")
    def test_startup_user_can_access_schemes(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {
                "source_page_url": "https://www.startupindia.gov.in/schemes",
                "api_url": "https://api.startupindia.gov.in",
                "scheme_count": 2,
                "group_count": 2,
            },
            "schemes": [
                {
                    "scheme_name": "Agri Innovation",
                    "ministry": "Ministry of Agriculture",
                    "brief": "Agri tech funding",
                    "benefit_tags": ["Grant"],
                },
                {
                    "scheme_name": "Cyber Defense",
                    "ministry": "Ministry of Defence",
                    "brief": "Defense security startup fund",
                    "benefit_tags": ["Defense"],
                },
            ],
        }
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/radar/schemes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"]["scheme_count"], 2)
        self.assertEqual(len(response.data["schemes"]), 2)

    @patch("intelligence.views.get_startup_schemes")
    def test_filter_by_ministry(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 2},
            "schemes": [
                {"scheme_name": "Scheme A", "ministry": "Ministry of Agriculture"},
                {"scheme_name": "Scheme B", "ministry": "Ministry of Defence"},
            ],
        }
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/radar/schemes/?ministry=Agriculture")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"]["scheme_count"], 1)
        self.assertEqual(response.data["schemes"][0]["scheme_name"], "Scheme A")

    @patch("intelligence.views.get_startup_schemes")
    def test_filter_by_search(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 2},
            "schemes": [
                {"scheme_name": "Drone Surveillance", "ministry": "Ministry of Defence", "brief": "Security drones", "benefit_tags": ["Defense"]},
                {"scheme_name": "Bio Fuel", "ministry": "Ministry of Energy", "brief": "Renewable fuel", "benefit_tags": ["Energy"]},
            ],
        }
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/radar/schemes/?search=drone")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"]["scheme_count"], 1)
        self.assertEqual(response.data["schemes"][0]["scheme_name"], "Drone Surveillance")

    def test_invalid_timeout_param(self):
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/radar/schemes/?timeout=invalid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timeout must be a positive integer", response.data["detail"])

    @patch("intelligence.views.get_startup_schemes")
    def test_upstream_request_error_returns_502(self, mock_scrape):
        mock_scrape.side_effect = requests.RequestException("Connection timeout")
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/radar/schemes/")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("Failed to fetch schemes", response.data["detail"])


class DirectGovernmentSchemesAPITests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.startup_user = User.objects.create_user(
            email="startup-direct-schemes@example.com",
            password="strongpassword123",
            name="Startup Direct User",
            user_type=UserType.STARTUP,
        )
        StartupProfile.objects.create(
            user=self.startup_user,
            company_name="DirectSchemeStartup",
            description="Testing direct schemes",
            industry="IT",
            technologies=["Django"],
            team_size=3,
        )
        self.gov_user = User.objects.create_user(
            email="gov-direct-schemes@example.com",
            password="strongpassword123",
            name="Gov Direct User",
            user_type=UserType.GOVERNMENT,
        )
        GovernmentProfile.objects.create(
            user=self.gov_user,
            department_name="Department of IT",
        )

    def test_direct_schemes_unauthenticated_denied(self):
        response = self.client.get("/api/schemes/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_direct_schemes_government_forbidden(self):
        self.client.force_authenticate(self.gov_user)
        response = self.client.get("/api/schemes/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("intelligence.views.get_startup_schemes")
    def test_direct_schemes_startup_access_success(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 1, "group_count": 1},
            "schemes": [
                {
                    "scheme_name": "Direct Scheme",
                    "ministry": "Ministry of Science",
                    "brief": "R&D funding for startups",
                    "sectors": ["DeepTech"],
                    "benefit_tags": ["Grant"],
                }
            ],
        }
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/schemes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["schemes"][0]["scheme_name"], "Direct Scheme")
        self.assertIn("results", response.data)
        self.assertIn("metadata", response.data)

    @patch("intelligence.views.get_startup_schemes")
    def test_direct_schemes_format_array(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 1},
            "schemes": [{"scheme_name": "Direct Scheme"}],
        }
        self.client.force_authenticate(self.startup_user)
        response = self.client.get("/api/schemes/?output=array")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data[0]["scheme_name"], "Direct Scheme")

    @patch("intelligence.views.get_startup_schemes")
    def test_direct_schemes_caching_and_refresh(self, mock_scrape):
        mock_scrape.return_value = {
            "metadata": {"scheme_count": 1},
            "schemes": [{"scheme_name": "Cached Scheme"}],
        }
        self.client.force_authenticate(self.startup_user)
        # First call fetches and caches
        res1 = self.client.get("/api/schemes/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.data["metadata"]["cached"])
        self.assertEqual(mock_scrape.call_count, 1)

        # Second call returns from cache
        res2 = self.client.get("/api/schemes/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["metadata"]["cached"])
        self.assertEqual(mock_scrape.call_count, 1)

        # Force refresh calls scraper again
        res3 = self.client.get("/api/schemes/?refresh=true")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertFalse(res3.data["metadata"]["cached"])
        self.assertEqual(mock_scrape.call_count, 2)
