from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MilestoneViewSet, PilotEvidenceViewSet, PilotViewSet

router = DefaultRouter()
router.register("", PilotViewSet, basename="pilot")
router.register("milestones", MilestoneViewSet, basename="milestone")
router.register("evidence-records", PilotEvidenceViewSet, basename="pilot-evidence")

urlpatterns = [
    path("", include(router.urls)),
]
