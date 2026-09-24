from django.contrib import admin

from .models import OBU, Company, Driver, Vehicle
from .services import VehicleService


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
    list_select_related = ('company', 'assigned_manager', 'driver__user')
    search_fields = ('vehicle_id', 'license_plate', 'vin')
    ordering = ('-created_at',)
    autocomplete_fields = ('company', 'assigned_manager', 'driver')

    def save_model(self, request, obj, form, change):
        previous_manager_id = None
        if change:
            previous_manager_id = (
                Vehicle.objects.filter(pk=obj.pk).values_list('assigned_manager_id', flat=True).first()
            )
        super().save_model(request, obj, form, change)
        VehicleService._invalidate_caches(
            obj.id, [previous_manager_id, obj.assigned_manager_id], obj.vehicle_id,
        )

    def delete_model(self, request, obj):
        vehicle_id, manager_id, public_id = obj.id, obj.assigned_manager_id, obj.vehicle_id
        super().delete_model(request, obj)
        VehicleService._invalidate_caches(vehicle_id, [manager_id], public_id)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('license_number', 'user', 'phone_number', 'is_active', 'created_at')
    list_filter = ('is_active',)
    list_select_related = ('user',)
    search_fields = ('license_number', 'phone_number', 'user__username', 'user__email')
    autocomplete_fields = ('user',)


@admin.register(OBU)
class OBUAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'vehicle', 'firmware_version', 'is_active', 'installed_at')
    list_select_related = ('vehicle',)
    search_fields = ('serial_number', 'vehicle__vehicle_id')
    autocomplete_fields = ('vehicle',)