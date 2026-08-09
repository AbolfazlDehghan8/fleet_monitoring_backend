from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('auth_module.urls')),
    path('api/v1/admin/', include('auth_module.admin_urls')),
    path('api/v1/vehicles/', include('vehicles_module.urls')),
    path('api/v1/telemetry/', include('telemetry_module.urls')),
    path('api/v1/rules/', include('rules_module.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]