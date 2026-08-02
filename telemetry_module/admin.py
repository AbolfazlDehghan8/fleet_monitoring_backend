from django.contrib import admin
from .models import TelemetryLog


@admin.register(TelemetryLog)
class TelemetryLogAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'obu_serial', 'timestamp', 'speed', 'fuel_level', 'received_at')
    list_filter = ('vehicle',)
    search_fields = ('vehicle__vehicle_id', 'obu_serial')
    ordering = ('-timestamp',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False