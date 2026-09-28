import hashlib
import logging

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied, Throttled
from rest_framework.exceptions import ValidationError as DRFValidationError

from vehicles_module.models import Driver, Vehicle

from . import tokens
from .models import RefreshToken, User

audit_logger = logging.getLogger('audit')


def _integrity_to_validation_error(exc):
    constraint = getattr(getattr(exc.__cause__, 'diag', None), 'constraint_name', None)
    if not constraint:
        constraint = str(exc).split('DETAIL')[0]
    constraint = constraint.lower()
    if 'username' in constraint:
        return ValidationError({'username': 'Username already exists'})
    if 'email' in constraint:
        return ValidationError({'email': 'Email already exists'})
    return ValidationError({'detail': 'Could not create user due to a conflicting record'})


def _revoke_all_refresh_tokens(user_id):
    return RefreshToken.objects.filter(user_id=user_id, revoked=False).update(revoked=True)


def _require_admin(actor, action, message, target=None):
    if not (actor and getattr(actor, 'is_authenticated', False) and actor.is_admin):
        audit_logger.warning(
            f'unauthorized_{action}_attempt',
            extra={'actor': getattr(actor, 'id', None), 'action': action, 'target': target},
        )
        raise PermissionDenied(message)


def _login_failure_key(username, ip_address):
    digest = hashlib.sha256(f'{username.lower()}|{ip_address or "-"}'.encode()).hexdigest()[:32]
    return f'auth:login_failures:{digest}'


class AuthService:

    @staticmethod
    def _create_user(validated_data, role):
        email = validated_data['email'].strip().lower()
        unsaved_user = User(
            username=validated_data['username'],
            email=email,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        try:
            validate_password(validated_data['password'], user=unsaved_user)
        except ValidationError as exc:
            raise ValidationError({'password': exc.messages})

        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=validated_data['username'],
                    email=email,
                    password=validated_data['password'],
                    role=role,
                    first_name=validated_data.get('first_name', ''),
                    last_name=validated_data.get('last_name', ''),
                )
        except IntegrityError as exc:
            raise _integrity_to_validation_error(exc)

    @staticmethod
    def register_user(validated_data):
        user = AuthService._create_user(validated_data, role=User.Role.DRIVER)
        audit_logger.info(
            'user_registered', extra={'actor': user.id, 'action': 'register', 'target': user.id}
        )
        return user

    @staticmethod
    def admin_create_user(actor, validated_data):
        _require_admin(actor, 'admin_create_user', 'Only admins may provision users.')
        role = validated_data.get('role', User.Role.DRIVER)
        user = AuthService._create_user(validated_data, role=role)
        audit_logger.info(
            'user_created_by_admin',
            extra={'actor': actor.id, 'action': 'admin_create_user', 'target': user.id, 'role': role},
        )
        return user

    @staticmethod
    def _check_login_lockout(key, username, ip_address):
        failures = cache.get(key) or 0
        if failures >= settings.AUTH_MAX_FAILED_LOGINS:
            audit_logger.warning(
                'login_blocked_too_many_failures',
                extra={'actor': username, 'action': 'login_blocked', 'target': ip_address},
            )
            ttl = cache.ttl(key) if hasattr(cache, 'ttl') else None
            raise Throttled(
                wait=ttl or settings.AUTH_LOCKOUT_SECONDS,
                detail='Too many failed login attempts. Try again later.',
            )

    @staticmethod
    def _register_login_failure(key):
        cache.add(key, 0, timeout=settings.AUTH_LOCKOUT_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=settings.AUTH_LOCKOUT_SECONDS)

    @staticmethod
    def login_user(username, password, ip_address=None):
        key = _login_failure_key(username, ip_address)
        AuthService._check_login_lockout(key, username, ip_address)

        user = authenticate(username=username, password=password)

        if not user:
            AuthService._register_login_failure(key)
            audit_logger.warning(
                'login_failed', extra={'actor': username, 'action': 'login_failed', 'target': ip_address}
            )
            raise AuthenticationFailed('Invalid username or password')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        cache.delete(key)

        access_token, _ = tokens.encode(user, tokens.ACCESS, tokens.access_lifetime())
        refresh_token = AuthService._issue_refresh_token(user)

        audit_logger.info('user_login', extra={'actor': user.id, 'action': 'login', 'target': user.id})

        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'access_token': access_token,
            'refresh_token': refresh_token,
        }

    @staticmethod
    def refresh_access_token(refresh_token):
        try:
            payload = tokens.decode(refresh_token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid refresh token')

        if payload.get('type') != tokens.REFRESH:
            raise AuthenticationFailed('Invalid token type. Use refresh token.')

        jti = payload.get('jti')
        if not jti:
            raise AuthenticationFailed('Invalid refresh token')

        reused_by_user_id = None
        with transaction.atomic():
            try:
                token_record = (
                    RefreshToken.objects.select_for_update(of=('self',))
                    .select_related('user')
                    .get(jti=jti)
                )
            except (RefreshToken.DoesNotExist, ValueError, ValidationError):
                raise AuthenticationFailed('Refresh token has been revoked or does not exist')

            if token_record.revoked:
                reused_by_user_id = token_record.user_id
            else:
                user = token_record.user
                if not user.is_active:
                    raise AuthenticationFailed('User account is disabled')

                access_token, _ = tokens.encode(user, tokens.ACCESS, tokens.access_lifetime())
                new_refresh_token = AuthService._issue_refresh_token(user, replaces=token_record)

        if reused_by_user_id is not None:
            audit_logger.warning(
                'refresh_token_reuse_detected',
                extra={'actor': reused_by_user_id, 'action': 'refresh_reuse', 'target': reused_by_user_id},
            )
            _revoke_all_refresh_tokens(reused_by_user_id)
            raise AuthenticationFailed('Refresh token has been revoked')

        audit_logger.info('token_refreshed', extra={'actor': user.id, 'action': 'refresh', 'target': user.id})
        return {'access_token': access_token, 'refresh_token': new_refresh_token}

    @staticmethod
    def logout_user(user, refresh_token=None):
        if refresh_token:
            try:
                payload = tokens.decode(refresh_token)
                jti = payload.get('jti')
                if jti:
                    RefreshToken.objects.filter(jti=jti, user=user).update(revoked=True)
            except (jwt.InvalidTokenError, ValidationError, ValueError):
                pass

        audit_logger.info('user_logout', extra={'actor': user.id, 'action': 'logout', 'target': user.id})

    @staticmethod
    def _issue_refresh_token(user, replaces=None):
        token, payload = tokens.encode(user, tokens.REFRESH, tokens.refresh_lifetime())

        RefreshToken.objects.create(
            jti=payload['jti'], user=user, issued_at=payload['iat'], expires_at=payload['exp'],
        )

        if replaces is not None:
            replaces.revoked = True
            replaces.replaced_by = payload['jti']
            replaces.save(update_fields=['revoked', 'replaced_by'])

        return token


class UserService:

    @staticmethod
    def get_user_by_id(user_id):
        return User.objects.get(id=user_id)

    @staticmethod
    def list_users(role=None):
        queryset = User.objects.all().order_by('-created_at', '-id')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    @staticmethod
    def update_user_profile(user, data):
        for field in ('first_name', 'last_name', 'email'):
            if field in data:
                setattr(user, field, data[field])

        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            raise ValidationError({'email': 'Email already exists'})

        audit_logger.info('profile_updated', extra={'actor': user.id, 'action': 'update_profile', 'target': user.id})
        return user

    @staticmethod
    def change_password(user, old_password, new_password):
        if not user.check_password(old_password):
            raise DRFValidationError({'error': ['Current password is incorrect']})

        if old_password == new_password:
            raise DRFValidationError({'new_password': ['New password must be different from the current password']})

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            raise ValidationError({'new_password': exc.messages})

        with transaction.atomic():
            user.set_password(new_password)
            user.save()
            _revoke_all_refresh_tokens(user.id)

        audit_logger.info('password_changed', extra={'actor': user.id, 'action': 'change_password', 'target': user.id})
        return True

    @staticmethod
    def _assert_not_last_active_admin(user):
        active_admin_ids = list(
            User.objects.select_for_update()
            .filter(role=User.Role.ADMIN, is_active=True)
            .order_by('id')
            .values_list('id', flat=True)
        )
        if not set(active_admin_ids) - {user.id}:
            raise DRFValidationError({'detail': ['Cannot remove the last active admin']})

    @staticmethod
    def admin_update_user(actor, user_id, data):
        _require_admin(actor, 'admin_update_user', 'Only admins may update other users.', target=user_id)

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(id=user_id)
            except User.DoesNotExist:
                raise NotFound('User not found')

            previous_role = user.role
            new_role = data.get('role', user.role)
            new_active = data.get('is_active', user.is_active)
            loses_admin = user.is_admin and user.is_active and (new_role != User.Role.ADMIN or not new_active)

            if loses_admin:
                if user.id == actor.id:
                    raise DRFValidationError({'detail': ['You cannot demote or deactivate your own account']})
                UserService._assert_not_last_active_admin(user)

            for field in ('first_name', 'last_name', 'email', 'role', 'is_active'):
                if field in data:
                    setattr(user, field, data[field])

            try:
                user.save()
            except IntegrityError:
                raise ValidationError({'email': 'Email already exists'})

            if not new_active:
                _revoke_all_refresh_tokens(user.id)

            UserService._sync_role_side_effects(user, previous_role, new_role, new_active)

        audit_logger.info('user_updated_by_admin', extra={'actor': actor.id, 'action': 'admin_update_user', 'target': user.id})
        return user

    @staticmethod
    def _sync_role_side_effects(user, previous_role, new_role, new_active):
        stops_being_driver = previous_role == User.Role.DRIVER and (
            new_role != User.Role.DRIVER or not new_active
        )
        if stops_being_driver:
            driver_profile = Driver.objects.filter(user_id=user.id).first()
            if driver_profile:
                Vehicle.objects.filter(driver_id=driver_profile.id).update(driver=None)
                if driver_profile.is_active:
                    driver_profile.is_active = False
                    driver_profile.save(update_fields=['is_active', 'updated_at'])

        stops_being_manager = previous_role == User.Role.FLEET_MANAGER and (
            new_role != User.Role.FLEET_MANAGER or not new_active
        )
        if stops_being_manager:
            Vehicle.objects.filter(assigned_manager_id=user.id).update(assigned_manager=None)

    @staticmethod
    def delete_user(actor, user_id):
        _require_admin(actor, 'delete_user', 'Only admins may delete users.', target=user_id)

        with transaction.atomic():
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise NotFound('User not found')

            if user.id == actor.id:
                raise DRFValidationError({'detail': ['You cannot delete your own account']})
            if user.is_admin and user.is_active:
                UserService._assert_not_last_active_admin(user)

            audit_logger.info('user_deleted_by_admin', extra={'actor': actor.id, 'action': 'delete_user', 'target': user_id})
            user.delete()