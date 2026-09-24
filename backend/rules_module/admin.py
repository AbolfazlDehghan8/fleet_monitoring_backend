from django.contrib import admin

from .models import Rule
from .services import invalidate_active_rules_cache


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'metric', 'operator', 'threshold', 'severity', 'is_active', 'created_by')
    list_filter = ('metric', 'severity', 'is_active')
    list_select_related = ('created_by',)
    search_fields = ('name',)
    autocomplete_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        invalidate_active_rules_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_active_rules_cache()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        invalidate_active_rules_cache()