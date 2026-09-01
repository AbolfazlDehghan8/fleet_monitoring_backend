from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import RefreshToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Fleet Monitoring', {'fields': ('role',)}),
    )


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ('jti', 'user', 'issued_at', 'expires_at', 'revoked')
    list_filter = ('revoked',)
    search_fields = ('user__username', 'jti')
    readonly_fields = ('jti', 'user', 'issued_at', 'expires_at', 'replaced_by')
    ordering = ('-issued_at',)
