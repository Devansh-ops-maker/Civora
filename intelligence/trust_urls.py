from django.urls import path

from .trust_views import TrustGraphViewSet

urlpatterns = [
    path(
        "startups/<uuid:startup_id>/",
        TrustGraphViewSet.as_view({"get": "startup"}),
        name="trust-graph-startup",
    ),
    path(
        "pilots/<uuid:pilot_id>/",
        TrustGraphViewSet.as_view({"get": "pilot"}),
        name="trust-graph-pilot",
    ),
    path(
        "challenges/<uuid:challenge_id>/",
        TrustGraphViewSet.as_view({"get": "challenge"}),
        name="trust-graph-challenge",
    ),
]
