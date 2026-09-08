from rest_framework import serializers

from auth_module.models import User

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


class DriverCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='driver'))
    license_number = serializers.CharField(max_length=50)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_user(self, user):
        if Driver.objects.filter(user=user).exists():
            raise serializers.ValidationError('This user already has a driver profile')
        return user


class DriverUpdateSerializer(serializers.Serializer):
    license_number = serializers.CharField(max_length=50, required=False)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


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


class VehicleCreateSerializer(serializers.Serializer):
    vehicle_id = serializers.CharField(max_length=50)
    license_plate = serializers.CharField(max_length=20)
    vin = serializers.CharField(max_length=17, required=False, allow_null=True, allow_blank=True)
    make = serializers.CharField(max_length=50, required=False, allow_blank=True)
    model = serializers.CharField(max_length=50, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Vehicle.Status.choices, required=False)
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    assigned_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='fleet_manager'), required=False, allow_null=True
    )
    obu_serial_number = serializers.CharField(max_length=50, required=False)
    obu_firmware_version = serializers.CharField(max_length=20, required=False, allow_blank=True)

class VehicleAdminUpdateSerializer(serializers.Serializer):
    license_plate = serializers.CharField(max_length=20, required=False)
    vin = serializers.CharField(max_length=17, required=False, allow_null=True, allow_blank=True)
    make = serializers.CharField(max_length=50, required=False, allow_blank=True)
    model = serializers.CharField(max_length=50, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Vehicle.Status.choices, required=False)
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    assigned_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='fleet_manager'), required=False, allow_null=True
    )
    obu_serial_number = serializers.CharField(max_length=50, required=False)
    obu_firmware_version = serializers.CharField(max_length=20, required=False, allow_blank=True)


class VehicleManagerUpdateSerializer(serializers.Serializer):
    license_plate = serializers.CharField(max_length=20, required=False)
    vin = serializers.CharField(max_length=17, required=False, allow_null=True, allow_blank=True)
    make = serializers.CharField(max_length=50, required=False, allow_blank=True)
    model = serializers.CharField(max_length=50, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Vehicle.Status.choices, required=False)
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    obu_serial_number = serializers.CharField(max_length=50, required=False)
    obu_firmware_version = serializers.CharField(max_length=20, required=False, allow_blank=True)

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'registration_number', 'address',
            'contact_email', 'contact_phone', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    registration_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)