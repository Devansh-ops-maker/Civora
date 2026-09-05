from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RadarViewSet

router = DefaultRouter()
router.register("", RadarViewSet, basename="radar")

urlpatterns = [
    path("", include(router.urls)),
]
