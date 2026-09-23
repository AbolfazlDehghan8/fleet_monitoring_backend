import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


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

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(Lower('username'), name='auth_user_username_ci_unique'),
            models.UniqueConstraint(Lower('email'), name='auth_user_email_ci_unique'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.is_superuser and self.role != self.Role.ADMIN:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_fleet_manager(self):
        return self.role == self.Role.FLEET_MANAGER

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER


class RefreshToken(models.Model):
    jti = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    revoked = models.BooleanField(default=False)
    replaced_by = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'revoked']),
        ]

    def __str__(self):
        return f"RefreshToken({self.jti}) user={self.user_id} revoked={self.revoked}"