from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Driver(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_profile',
    )
    license_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drivers'
        indexes = [models.Index(fields=['license_number'])]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.license_number})"

    def clean(self):
        if self.user_id and self.user.role != 'driver':
            raise ValidationError({'user': 'Linked user must have the driver role'})


class Vehicle(models.Model):

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        MAINTENANCE = 'maintenance', 'Maintenance'
        INACTIVE = 'inactive', 'Inactive'
        DECOMMISSIONED = 'decommissioned', 'Decommissioned'

    vehicle_id = models.CharField(max_length=50, unique=True, db_index=True)

    license_plate = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True, null=True, blank=True)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicles',
    )

    assigned_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_vehicles',
        limit_choices_to={'role': 'fleet_manager'},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vehicle_id']),
            models.Index(fields=['assigned_manager']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.vehicle_id} ({self.license_plate})"

    def clean(self):
        if self.assigned_manager_id and self.assigned_manager.role != 'fleet_manager':
            raise ValidationError({'assigned_manager': 'Assigned manager must have the fleet_manager role'})


class OBU(models.Model):

    vehicle = models.OneToOneField(Vehicle, on_delete=models.CASCADE, related_name='obu')
    serial_number = models.CharField(max_length=50, unique=True)
    firmware_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    installed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'obus'
        indexes = [models.Index(fields=['serial_number'])]

    def __str__(self):
        return self.serial_number