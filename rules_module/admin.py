from django.contrib import admin

from .models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'metric', 'operator', 'threshold', 'severity', 'is_active', 'created_by')
    list_filter = ('metric', 'severity', 'is_active')
    search_fields = ('name',)
