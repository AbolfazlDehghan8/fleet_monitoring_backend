from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'requested_by', 'vehicle_id', 'status', 'created_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('vehicle_id', 'requested_by__username')
    autocomplete_fields = ('requested_by',)