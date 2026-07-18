from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        FLEET_MANAGER = 'fleet_manager', 'Fleet Manager'
        DRIVER = 'driver', 'Driver'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DRIVER,
        db_index=True
    )
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ['email', 'role']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_fleet_manager(self):
        return self.role == self.Role.FLEET_MANAGER

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER