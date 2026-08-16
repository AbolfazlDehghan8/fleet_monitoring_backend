from django.urls import path

from .views import AlertAcknowledgeView, AlertDetailView, AlertListView, AlertMeView

urlpatterns = [
    path('', AlertListView.as_view(), name='alert-list'),
    path('me/', AlertMeView.as_view(), name='alert-me'),
    path('<int:alert_id>/', AlertDetailView.as_view(), name='alert-detail'),
    path('<int:alert_id>/acknowledge/', AlertAcknowledgeView.as_view(), name='alert-acknowledge'),
]
