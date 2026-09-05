from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/startups/", include("startups.urls")),
    path("api/challenges/", include("challenges.urls")),
    path("api/applications/", include("evaluations.urls")),
    path("api/radar/", include("intelligence.urls")),
    path("api/pilots/", include("pilots.urls")),
    path("api/trust-graph/", include("intelligence.trust_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
