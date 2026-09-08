from django.urls import path

from .views import (
    CompanyView,
    DashboardStatsView,
    DriverDetailView,
    DriverListCreateView,
    VehicleDetailView,
    VehicleListCreateView,
    VehicleMeView,
    VehicleStatusView,
)

urlpatterns = [
    path('me/', VehicleMeView.as_view(), name='vehicle-me'),
    path('dashboard-stats/', DashboardStatsView.as_view(), name='vehicle-dashboard-stats'),
    path('drivers/', DriverListCreateView.as_view(), name='driver-list-create'),
    path('drivers/<int:driver_id>/', DriverDetailView.as_view(), name='driver-detail'),
    path('company/', CompanyView.as_view(), name='company-detail'),
    path('', VehicleListCreateView.as_view(), name='vehicle-list-create'),
    path('<int:vehicle_id>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    path('<int:vehicle_id>/status/', VehicleStatusView.as_view(), name='vehicle-status'),
]