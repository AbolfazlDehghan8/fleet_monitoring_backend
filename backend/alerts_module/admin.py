from django.contrib import admin
from django.db.models import Count

from .models import Alert, AlertAcknowledgment, AlertDismissal


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'vehicle', 'severity', 'value', 'threshold', 'acknowledgment_count', 'created_at')
    list_filter = ('severity',)
    list_select_related = ('vehicle',)
    search_fields = ('vehicle__vehicle_id', 'rule_name')
    raw_id_fields = ('vehicle', 'telemetry_log')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_ack_count=Count('acknowledgments'))

    @admin.display(description='Acknowledgments', ordering='_ack_count')
    def acknowledgment_count(self, obj):
        return obj._ack_count

    def has_add_permission(self, request):
        return False


@admin.register(AlertAcknowledgment)
class AlertAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ('alert', 'user', 'created_at')
    raw_id_fields = ('alert', 'user')


@admin.register(AlertDismissal)
class AlertDismissalAdmin(admin.ModelAdmin):
    list_display = ('alert', 'user', 'created_at')
    raw_id_fields = ('alert', 'user')