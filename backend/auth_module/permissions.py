from rest_framework import permissions


class _RolePermission(permissions.BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsAdmin(_RolePermission):
    allowed_roles = ('admin',)


class IsFleetManager(_RolePermission):
    allowed_roles = ('fleet_manager',)


class IsDriver(_RolePermission):
    allowed_roles = ('driver',)


class IsAdminOrFleetManager(_RolePermission):
    allowed_roles = ('admin', 'fleet_manager')