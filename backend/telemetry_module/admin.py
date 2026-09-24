from django.contrib import admin

from .models import TelemetryLog


@admin.register(TelemetryLog)
class TelemetryLogAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'obu_serial', 'timestamp', 'speed', 'engine_temperature', 'fuel_level')
    list_select_related = ('vehicle',)
    raw_id_fields = ('vehicle',)
    search_fields = ('vehicle__vehicle_id', 'obu_serial')
    ordering = ('-timestamp',)
    list_per_page = 50
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False