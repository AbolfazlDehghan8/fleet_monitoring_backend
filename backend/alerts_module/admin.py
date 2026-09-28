from django.contrib import admin

from .models import Alert, AlertDismissal


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'vehicle', 'severity', 'value', 'threshold', 'acknowledged', 'created_at')
    list_filter = ('severity', 'acknowledged')
    list_select_related = ('vehicle', 'acknowledged_by')
    search_fields = ('vehicle__vehicle_id', 'rule_name')
    raw_id_fields = ('vehicle', 'telemetry_log')

    def has_add_permission(self, request):
        return False


@admin.register(AlertDismissal)
class AlertDismissalAdmin(admin.ModelAdmin):
    list_display = ('alert', 'user', 'created_at')
    raw_id_fields = ('alert', 'user')
