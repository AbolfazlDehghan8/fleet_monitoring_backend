from rest_framework import serializers

from auth_module.models import User
from fleet_monitoring.fields import NormalizedCharField
from fleet_monitoring.validators import (
    iran_driver_license_validator,
    iran_mobile_validator,
    iran_phone_validator,
    iran_plate_validator,
    obu_serial_validator,
    validate_vehicle_id,
    validate_vehicle_year,
)

from .models import OBU, Company, Driver, Vehicle


class OBUSerializer(serializers.ModelSerializer):
    class Meta:
        model = OBU
        fields = ['serial_number', 'firmware_version', 'is_active', 'installed_at']


class DriverSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'username', 'email', 'full_name',
            'license_number', 'phone_number', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username


class LinkableUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class VehicleSerializer(serializers.ModelSerializer):
    driver = DriverSerializer(read_only=True)
    obu = OBUSerializer(read_only=True)
    assigned_manager_username = serializers.CharField(
        source='assigned_manager.username', read_only=True, default=None
    )

    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_id', 'license_plate', 'vin', 'make', 'model', 'year', 'status',
            'driver', 'assigned_manager', 'assigned_manager_username', 'obu',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'registration_number', 'address',
            'contact_email', 'contact_phone', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VehicleFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Vehicle.Status.choices, required=False)
    search = NormalizedCharField(max_length=100, required=False)
    driver = serializers.IntegerField(required=False, min_value=1)
    assigned_manager = serializers.IntegerField(required=False, min_value=1)


class DriverFilterSerializer(serializers.Serializer):
    search = NormalizedCharField(max_length=100, required=False)


class DriverCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='driver'))
    license_number = NormalizedCharField(max_length=10, validators=[iran_driver_license_validator])
    phone_number = NormalizedCharField(
        max_length=11, required=False, allow_blank=True, validators=[iran_mobile_validator]
    )

    def validate_user(self, user):
        if Driver.objects.filter(user=user).exists():
            raise serializers.ValidationError('This user already has a driver profile')
        return user

    def validate_phone_number(self, value):
        if not value:
            return value
        if Driver.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('phone_number already exists')
        return value


class DriverUpdateSerializer(serializers.Serializer):
    license_number = NormalizedCharField(
        max_length=10, required=False, validators=[iran_driver_license_validator]
    )
    phone_number = NormalizedCharField(
        max_length=11, required=False, allow_blank=True, validators=[iran_mobile_validator]
    )
    is_active = serializers.BooleanField(required=False)

    def validate_phone_number(self, value):
        if not value:
            return value
        qs = Driver.objects.filter(phone_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('phone_number already exists')
        return value


class _VehicleWriteBase(serializers.Serializer):
    license_plate = NormalizedCharField(max_length=8, validators=[iran_plate_validator])
    vin = NormalizedCharField(max_length=17, required=False, allow_null=True, allow_blank=True)
    make = serializers.CharField(max_length=50, required=False, allow_blank=True)
    model = serializers.CharField(max_length=50, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True, validators=[validate_vehicle_year])
    status = serializers.ChoiceField(choices=Vehicle.Status.choices, required=False)
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    obu_serial_number = NormalizedCharField(
        max_length=50, required=False, allow_null=True, validators=[obu_serial_validator]
    )
    obu_firmware_version = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_vin(self, value):
        return (value.upper() or None) if value else None

    def validate_obu_serial_number(self, value):
        return value.upper() if value else value


class VehicleCreateSerializer(_VehicleWriteBase):
    vehicle_id = serializers.CharField(max_length=50, validators=[validate_vehicle_id])
    assigned_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='fleet_manager'), required=False, allow_null=True
    )


class VehicleAdminUpdateSerializer(_VehicleWriteBase):
    assigned_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='fleet_manager'), required=False, allow_null=True
    )


class VehicleManagerUpdateSerializer(_VehicleWriteBase):
    pass


class CompanyUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    registration_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = NormalizedCharField(
        max_length=11, required=False, allow_blank=True, validators=[iran_phone_validator]
    )