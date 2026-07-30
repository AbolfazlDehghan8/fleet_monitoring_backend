import logging
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from .models import RefreshToken, User


audit_logger = logging.getLogger('audit')

ACCESS_TOKEN_LIFETIME_MINUTES = 30
REFRESH_TOKEN_LIFETIME_DAYS = 7


class AuthService:

    @staticmethod
    def register_user(validated_data):
        # AUTH_PASSWORD_VALIDATORS (UserAttributeSimilarityValidator, MinimumLengthValidator,
        # CommonPasswordValidator, NumericPasswordValidator) must actually run, not just be
        # configured. We validate against an unsaved instance so attribute-similarity checks
        # (username/email/first_name/last_name) can also be enforced before the user exists.
        unsaved_user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        try:
            validate_password(validated_data['password'], user=unsaved_user)
        except ValidationError as exc:
            raise ValidationError({'password': exc.messages})

        try:
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                role=User.Role.DRIVER,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
            )
        except IntegrityError as exc:
            message = str(exc).lower()
            if 'username' in message:
                raise ValidationError({'username': 'Username already exists'})
            if 'email' in message:
                raise ValidationError({'email': 'Email already exists'})
            raise ValidationError({'detail': 'Could not create user due to a conflicting record'})

        audit_logger.info(
            'user_registered', extra={'actor': user.id, 'action': 'register', 'target': user.id}
        )
        return user

    @staticmethod
    def admin_create_user(actor, validated_data):
        # NFR-SEC02: RBAC must be enforced at the view layer AND the service layer.
        # This check is a deliberate second line of defense — it must not rely solely
        # on the view's `IsAdmin` permission class, so that this service stays safe
        # even if called from a future task/command/view that forgets that check.
        if not (actor and getattr(actor, 'is_authenticated', False) and actor.is_admin):
            audit_logger.warning(
                'unauthorized_admin_create_user_attempt',
                extra={'actor': getattr(actor, 'id', None), 'action': 'admin_create_user', 'target': None},
            )
            raise PermissionDenied('Only admins may provision users.')

        role = validated_data.get('role', User.Role.DRIVER)

        unsaved_user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        try:
            validate_password(validated_data['password'], user=unsaved_user)
        except ValidationError as exc:
            raise ValidationError({'password': exc.messages})

        try:
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                role=role,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
            )
        except IntegrityError as exc:
            message = str(exc).lower()
            if 'username' in message:
                raise ValidationError({'username': 'Username already exists'})
            if 'email' in message:
                raise ValidationError({'email': 'Email already exists'})
            raise ValidationError({'detail': 'Could not create user due to a conflicting record'})

        audit_logger.info(
            'user_created_by_admin', extra={'actor': actor.id, 'action': 'admin_create_user', 'target': user.id}
        )
        return user

    @staticmethod
    def login_user(username, password):
        from django.contrib.auth import authenticate

        user = authenticate(username=username, password=password)

        if not user:
            raise AuthenticationFailed('Invalid username or password')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        access_token = AuthService._generate_token(user, 'access', minutes=ACCESS_TOKEN_LIFETIME_MINUTES)
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
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload.get('type') != 'refresh':
                raise AuthenticationFailed('Invalid token type. Use refresh token.')

            jti = payload.get('jti')
            if not jti:
                raise AuthenticationFailed('Invalid refresh token')

            try:
                token_record = RefreshToken.objects.select_related('user').get(jti=jti)
            except (RefreshToken.DoesNotExist, ValueError):
                raise AuthenticationFailed('Refresh token has been revoked or does not exist')

            if token_record.revoked:
                audit_logger.info(
                    'refresh_token_reuse_detected',
                    extra={'actor': token_record.user_id, 'action': 'refresh_reuse', 'target': token_record.user_id},
                )
                RefreshToken.objects.filter(user_id=token_record.user_id, revoked=False).update(revoked=True)
                raise AuthenticationFailed('Refresh token has been revoked')

            user = token_record.user
            if not user.is_active:
                raise AuthenticationFailed('User account is disabled')

            access_token = AuthService._generate_token(user, 'access', minutes=ACCESS_TOKEN_LIFETIME_MINUTES)
            new_refresh_token = AuthService._issue_refresh_token(user, replaces=token_record)

            audit_logger.info('token_refreshed', extra={'actor': user.id, 'action': 'refresh', 'target': user.id})

            return {'access_token': access_token, 'refresh_token': new_refresh_token}

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid refresh token')

    @staticmethod
    def logout_user(user, refresh_token=None):
        if refresh_token:
            try:
                payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
                jti = payload.get('jti')
                if jti:
                    RefreshToken.objects.filter(jti=jti, user=user).update(revoked=True)
            except jwt.InvalidTokenError:
                pass

        audit_logger.info('user_logout', extra={'actor': user.id, 'action': 'logout', 'target': user.id})

    @staticmethod
    def _generate_token(user, token_type, minutes=0, days=0):
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=minutes) if token_type == 'access' else now + timedelta(days=days)

        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': expiry,
            'iat': now,
            'type': token_type,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def _issue_refresh_token(user, replaces=None):
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)
        jti = uuid.uuid4()

        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': expiry,
            'iat': now,
            'type': 'refresh',
            'jti': str(jti),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        RefreshToken.objects.create(jti=jti, user=user, issued_at=now, expires_at=expiry)

        if replaces is not None:
            replaces.revoked = True
            replaces.replaced_by = jti
            replaces.save(update_fields=['revoked', 'replaced_by'])

        return token


class UserService:

    @staticmethod
    def get_user_profile(user):
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'role_display': user.get_role_display(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'is_active': user.is_active,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
        }

    @staticmethod
    def get_user_by_id(user_id):
        return User.objects.get(id=user_id)

    @staticmethod
    def get_users_by_role(role):
        return User.objects.filter(role=role, is_active=True)

    @staticmethod
    def list_users(role=None):
        queryset = User.objects.all().order_by('-created_at')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    @staticmethod
    def update_user_profile(user, data):
        allowed_fields = ['first_name', 'last_name', 'email']
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        try:
            user.save()
        except IntegrityError:
            raise ValidationError({'email': 'Email already exists'})

        audit_logger.info('profile_updated', extra={'actor': user.id, 'action': 'update_profile', 'target': user.id})
        return user

    @staticmethod
    def change_password(user, old_password, new_password):
        if not user.check_password(old_password):
            raise AuthenticationFailed('Current password is incorrect')

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            raise ValidationError({'new_password': exc.messages})

        user.set_password(new_password)
        user.save()

        audit_logger.info('password_changed', extra={'actor': user.id, 'action': 'change_password', 'target': user.id})
        return True

    @staticmethod
    def admin_update_user(actor, user_id, data):
        # NFR-SEC02: second line of defense, independent of the view's IsAdmin permission.
        if not (actor and getattr(actor, 'is_authenticated', False) and actor.is_admin):
            audit_logger.warning(
                'unauthorized_admin_update_user_attempt',
                extra={'actor': getattr(actor, 'id', None), 'action': 'admin_update_user', 'target': user_id},
            )
            raise PermissionDenied('Only admins may update other users.')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'detail': 'User not found'})

        allowed_fields = ['first_name', 'last_name', 'email', 'role', 'is_active']
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        try:
            user.save()
        except IntegrityError:
            raise ValidationError({'email': 'Email already exists'})

        audit_logger.info('user_updated_by_admin', extra={'actor': actor.id, 'action': 'admin_update_user', 'target': user.id})
        return user

    @staticmethod
    def delete_user(actor, user_id):
        # NFR-SEC02: second line of defense, independent of the view's IsAdmin permission.
        if not (actor and getattr(actor, 'is_authenticated', False) and actor.is_admin):
            audit_logger.warning(
                'unauthorized_delete_user_attempt',
                extra={'actor': getattr(actor, 'id', None), 'action': 'delete_user', 'target': user_id},
            )
            raise PermissionDenied('Only admins may delete users.')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'detail': 'User not found'})

        audit_logger.info('user_deleted_by_admin', extra={'actor': actor.id, 'action': 'delete_user', 'target': user_id})
        user.delete()
