from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MyEvidenceDetailView,
    MyEvidenceListCreateView,
    MyPassportView,
    StartupEvidenceListView,
    StartupViewSet,
    VerifyEvidenceView,
)

router = DefaultRouter()
router.register("", StartupViewSet, basename="startup")

urlpatterns = [
    # Explicit paths first — they must be matched before the router's
    # catch-all "<pk>/" pattern below.
    path("passport/", MyPassportView.as_view(), name="my-passport"),
    path("passport/evidence/", MyEvidenceListCreateView.as_view(), name="my-evidence-list"),
    path(
        "passport/evidence/<uuid:evidence_id>/",
        MyEvidenceDetailView.as_view(),
        name="my-evidence-detail",
    ),
    path(
        "evidence/<uuid:evidence_id>/verify/",
        VerifyEvidenceView.as_view(),
        name="verify-evidence",
    ),
    path("<uuid:startup_id>/evidence/", StartupEvidenceListView.as_view(), name="startup-evidence-list"),
]

urlpatterns += router.urls
