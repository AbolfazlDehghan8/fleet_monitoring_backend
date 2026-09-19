from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from fleet_monitoring.validators import (
    iran_driver_license_validator,
    iran_mobile_validator,
    iran_phone_validator,
    iran_plate_validator,
    obu_serial_validator,
    vin_validator,
)


class Company(models.Model):

    name = models.CharField(max_length=150, unique=True)
    registration_number = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(
        max_length=11, blank=True, validators=[iran_phone_validator]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class Driver(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_profile',
    )
    license_number = models.CharField(
        max_length=10, unique=True, validators=[iran_driver_license_validator]
    )
    phone_number = models.CharField(
        max_length=11, blank=True, validators=[iran_mobile_validator]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drivers'
        indexes = [models.Index(fields=['license_number'])]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.license_number})"

    def clean(self):
        if self.user_id and not self.user.is_driver:
            raise ValidationError({'user': 'Linked user must have the driver role'})

        if self.phone_number:
            conflict = Driver.objects.filter(phone_number=self.phone_number)
            if self.pk:
                conflict = conflict.exclude(pk=self.pk)
            if conflict.exists():
                raise ValidationError({'phone_number': 'phone_number already exists'})

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('license_number',):
            return ValidationError('license_number already exists', code='unique')
        return super().unique_error_message(model_class, unique_check)


class Vehicle(models.Model):

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        MAINTENANCE = 'maintenance', 'Maintenance'
        INACTIVE = 'inactive', 'Inactive'
        DECOMMISSIONED = 'decommissioned', 'Decommissioned'

    vehicle_id = models.CharField(
        max_length=50, unique=True, db_index=True,
        error_messages={'unique': 'vehicle_id already exists'},
    )

    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='vehicles',
    )

    license_plate = models.CharField(
        max_length=8, unique=True, validators=[iran_plate_validator],
        error_messages={'unique': 'license_plate already exists'},
    )
    vin = models.CharField(
        max_length=17, unique=True, null=True, blank=True, validators=[vin_validator],
        error_messages={'unique': 'vin already exists'},
    )
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
        if self.assigned_manager_id and not self.assigned_manager.is_fleet_manager:
            original_manager_id = (
                Vehicle.objects.filter(pk=self.pk).values_list('assigned_manager_id', flat=True).first()
                if self.pk else None
            )
            if original_manager_id != self.assigned_manager_id:
                raise ValidationError({'assigned_manager': 'Assigned manager must have the fleet_manager role'})


class OBU(models.Model):

    vehicle = models.OneToOneField(Vehicle, on_delete=models.CASCADE, related_name='obu')
    serial_number = models.CharField(
        max_length=50, unique=True, validators=[obu_serial_validator],
        error_messages={'unique': 'serial_number already exists'},
    )
    firmware_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    installed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'obus'
        indexes = [models.Index(fields=['serial_number'])]

    def __str__(self):
        return self.serial_number