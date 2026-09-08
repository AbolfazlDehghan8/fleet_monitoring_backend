from django.contrib import admin

from .models import OBU, Company, Driver, Vehicle


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'contact_email', 'contact_phone', 'created_at')
    search_fields = ('name', 'registration_number', 'contact_email')

    def has_add_permission(self, request):
        if Company.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_id', 'license_plate', 'make', 'model', 'status',
        'company', 'assigned_manager', 'driver', 'created_at',
    )
    list_filter = ('status', 'make', 'company')
    search_fields = ('vehicle_id', 'license_plate', 'vin')
    ordering = ('-created_at',)
    autocomplete_fields = ('company', 'assigned_manager', 'driver')


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('license_number', 'user', 'is_active', 'created_at')
    search_fields = ('license_number', 'user__username', 'user__email')
    autocomplete_fields = ('user',)


@admin.register(OBU)
class OBUAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'vehicle', 'firmware_version', 'is_active', 'installed_at')
    search_fields = ('serial_number', 'vehicle__vehicle_id')
    autocomplete_fields = ('vehicle',)