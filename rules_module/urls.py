from django.urls import path

from .views import RuleDetailView, RuleListCreateView

urlpatterns = [
    path('', RuleListCreateView.as_view(), name='rule-list-create'),
    path('<int:rule_id>/', RuleDetailView.as_view(), name='rule-detail'),
]