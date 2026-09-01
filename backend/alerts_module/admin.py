from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'vehicle', 'severity', 'value', 'threshold', 'acknowledged', 'created_at')
    list_filter = ('severity', 'acknowledged')
    search_fields = ('vehicle__vehicle_id', 'rule_name')

    def has_add_permission(self, request):
        return False