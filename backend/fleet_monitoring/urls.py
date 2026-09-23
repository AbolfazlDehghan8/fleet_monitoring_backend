from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import health_check, metrics

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('metrics', metrics, name='prometheus-django-metrics'),
    path(settings.ADMIN_URL, admin.site.urls),
    path('api/v1/auth/', include('auth_module.urls')),
    path('api/v1/admin/', include('auth_module.admin_urls')),
    path('api/v1/vehicles/', include('vehicles_module.urls')),
    path('api/v1/telemetry/', include('telemetry_module.urls')),
    path('api/v1/rules/', include('rules_module.urls')),
    path('api/v1/alerts/', include('alerts_module.urls')),
    path('api/v1/reports/', include('reports_module.urls')),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]