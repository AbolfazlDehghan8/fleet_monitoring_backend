from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import RefreshToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Fleet Monitoring', {'fields': ('role', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ('jti', 'user', 'issued_at', 'expires_at', 'revoked')
    list_filter = ('revoked',)
    search_fields = ('user__username', 'jti')
    readonly_fields = ('jti', 'user', 'issued_at', 'expires_at', 'replaced_by')
    ordering = ('-issued_at',)
    list_select_related = ('user',)

    def has_add_permission(self, request):
        return False