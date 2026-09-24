from datetime import datetime, timedelta, timezone as dt_timezone

import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import RefreshToken, User
from rest_framework.exceptions import ValidationError as DRFValidationError

from .services import AuthService, UserService
from .tasks import cleanup_expired_refresh_tokens

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM_CACHE)
class AuthTestCase(APITestCase):
    def _pre_setup(self):
        super()._pre_setup()
        cache.clear()


class RegisterTests(AuthTestCase):
    def setUp(self):
        self.url = reverse('register')
        self.payload = {
            'username': 'driver01',
            'email': 'driver01@example.com',
            'password': 'StrongPass123',
            'password_confirm': 'StrongPass123',
            'role': 'driver',
            'first_name': 'Ali',
            'last_name': 'Rezaei',
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'driver')
        self.assertNotIn('password', response.data)

    def test_register_password_mismatch(self):
        self.payload['password_confirm'] = 'Different123'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username(self):
        self.client.post(self.url, self.payload)
        self.payload['email'] = 'other@example.com'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['username'], ['Username already exists'])
        self.assertNotIn('email', response.data)

    def test_register_duplicate_email(self):
        self.client.post(self.url, self.payload)
        self.payload['username'] = 'other_driver'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['email'], ['Email already exists'])
        self.assertNotIn('username', response.data)

    def test_register_duplicate_username_and_email_reports_both(self):
        self.client.post(self.url, self.payload)
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('email', response.data)

    def test_register_duplicate_is_case_insensitive(self):
        self.client.post(self.url, self.payload)
        self.payload['username'] = 'DRIVER01'
        self.payload['email'] = 'Driver01@Example.com'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('email', response.data)

    def test_register_role_field_is_ignored_not_validated(self):
        self.payload['role'] = 'super_admin'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'driver')

    def test_password_is_hashed_with_bcrypt(self):
        self.client.post(self.url, self.payload)
        user = User.objects.get(username='driver01')
        self.assertTrue(user.password.startswith('bcrypt_sha256$'))


class LoginTests(AuthTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='fleetmgr', email='fm@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.url = reverse('login')

    def test_login_success_returns_tokens(self):
        response = self.client.post(self.url, {'username': 'fleetmgr', 'password': 'StrongPass123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertEqual(response.data['user']['role'], 'fleet_manager')

    def test_login_invalid_credentials(self):
        response = self.client.post(self.url, {'username': 'fleetmgr', 'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_disabled_account(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {'username': 'fleetmgr', 'password': 'StrongPass123'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RefreshTokenTests(AuthTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='driver02', email='d2@example.com', password='StrongPass123', role='driver'
        )
        login = self.client.post(reverse('login'), {'username': 'driver02', 'password': 'StrongPass123'})
        self.refresh_token = login.data['refresh_token']

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(reverse('refresh'), {'refresh_token': self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)

    def test_refresh_with_invalid_token(self):
        response = self.client.post(reverse('refresh'), {'refresh_token': 'garbage'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTests(AuthTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='driver03', email='d3@example.com', password='StrongPass123', role='driver'
        )
        login = self.client.post(reverse('login'), {'username': 'driver03', 'password': 'StrongPass123'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

    def test_get_profile_requires_auth(self):
        anon_client = self.client_class()
        response = anon_client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_own_profile(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'driver03')

    def test_update_own_profile(self):
        response = self.client.patch(reverse('profile'), {'first_name': 'Sara'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Sara')

    def test_change_password(self):
        response = self.client.post(reverse('change-password'), {
            'old_password': 'StrongPass123',
            'new_password': 'NewStrongPass456',
            'new_password_confirm': 'NewStrongPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password(self):
        response = self.client.post(reverse('change-password'), {
            'old_password': 'wrongpass',
            'new_password': 'NewStrongPass456',
            'new_password_confirm': 'NewStrongPass456',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_change_password_same_as_old_password_rejected(self):
        response = self.client.post(reverse('change-password'), {
            'old_password': 'StrongPass123',
            'new_password': 'StrongPass123',
            'new_password_confirm': 'StrongPass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('StrongPass123'))


class AdminUserManagementTests(AuthTestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin01', email='admin01@example.com', password='StrongPass123', role='admin'
        )
        self.driver = User.objects.create_user(
            username='driver04', email='d4@example.com', password='StrongPass123', role='driver'
        )

    def _login_as(self, username, password):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

    def test_admin_can_list_users(self):
        self._login_as('admin01', 'StrongPass123')
        response = self.client.get(reverse('admin-user-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_non_admin_cannot_list_users(self):
        self._login_as('driver04', 'StrongPass123')
        response = self.client.get(reverse('admin-user-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_user_role(self):
        self._login_as('admin01', 'StrongPass123')
        response = self.client.patch(
            reverse('admin-user-detail', args=[self.driver.id]), {'role': 'fleet_manager'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.role, 'fleet_manager')

    def test_admin_can_deactivate_user(self):
        self._login_as('admin01', 'StrongPass123')
        response = self.client.patch(
            reverse('admin-user-detail', args=[self.driver.id]), {'is_active': False}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.driver.refresh_from_db()
        self.assertFalse(self.driver.is_active)

    def test_admin_can_delete_user(self):
        self._login_as('admin01', 'StrongPass123')
        response = self.client.delete(reverse('admin-user-detail', args=[self.driver.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.driver.id).exists())

    def test_non_admin_cannot_delete_user(self):
        self._login_as('driver04', 'StrongPass123')
        response = self.client.delete(reverse('admin-user-detail', args=[self.admin.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_user_with_any_role(self):
        self._login_as('admin01', 'StrongPass123')
        response = self.client.post(reverse('admin-user-list'), {
            'username': 'newmanager', 'email': 'nm@example.com',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
            'role': 'fleet_manager', 'first_name': 'New', 'last_name': 'Manager',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'fleet_manager')

    def test_non_admin_cannot_create_user(self):
        self._login_as('driver04', 'StrongPass123')
        response = self.client.post(reverse('admin-user-list'), {
            'username': 'newmanager2', 'email': 'nm2@example.com',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
            'role': 'fleet_manager',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RegisterPrivilegeEscalationTests(AuthTestCase):

    def test_self_register_ignores_role_field_and_forces_driver(self):
        url = reverse('register')
        payload = {
            'username': 'hacker', 'email': 'hacker@example.com',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
            'role': 'admin', 'first_name': 'H', 'last_name': 'K',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'driver')

        user = User.objects.get(username='hacker')
        self.assertEqual(user.role, User.Role.DRIVER)
        self.assertFalse(user.is_admin)

    def test_register_ignores_elevated_role_for_fleet_manager_too(self):
        url = reverse('register')
        response = self.client.post(url, {
            'username': 'hacker2', 'email': 'hacker2@example.com',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
            'role': 'fleet_manager',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'driver')


class RefreshTokenRotationTests(AuthTestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rotate01', email='rotate01@example.com', password='StrongPass123', role='driver'
        )
        login = self.client.post(reverse('login'), {'username': 'rotate01', 'password': 'StrongPass123'})
        self.first_refresh_token = login.data['refresh_token']

    def test_refresh_rotates_and_returns_new_refresh_token(self):
        response = self.client.post(reverse('refresh'), {'refresh_token': self.first_refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertNotEqual(response.data['refresh_token'], self.first_refresh_token)

    def test_old_refresh_token_cannot_be_reused_after_rotation(self):
        self.client.post(reverse('refresh'), {'refresh_token': self.first_refresh_token})
        response = self.client.post(reverse('refresh'), {'refresh_token': self.first_refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reuse_of_rotated_token_revokes_whole_chain(self):
        first_rotation = self.client.post(reverse('refresh'), {'refresh_token': self.first_refresh_token})
        new_refresh_token = first_rotation.data['refresh_token']

        self.client.post(reverse('refresh'), {'refresh_token': self.first_refresh_token})

        response = self.client.post(reverse('refresh'), {'refresh_token': new_refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_revokes_refresh_token(self):
        login = self.client.post(reverse('login'), {'username': 'rotate01', 'password': 'StrongPass123'})
        access_token = login.data['access_token']
        refresh_token = login.data['refresh_token']

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = self.client.post(reverse('logout'), {'refresh_token': refresh_token})
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(reverse('refresh'), {'refresh_token': refresh_token})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


def _make_token(user_id, token_type='access', lifetime=timedelta(minutes=5), key=None, drop=(), **extra):
    now = datetime.now(dt_timezone.utc)
    payload = {
        'user_id': user_id, 'username': 'x', 'role': 'driver', 'type': token_type,
        'iat': now, 'exp': now + lifetime, 'jti': '00000000-0000-0000-0000-000000000001',
    }
    payload.update(extra)
    for claim in drop:
        payload.pop(claim, None)
    return jwt.encode(payload, key or settings.JWT_SIGNING_KEY, algorithm='HS256')


def _login(client, username, password='StrongPass123'):
    return client.post(reverse('login'), {'username': username, 'password': password})


class JWTAuthenticationHardeningTests(AuthTestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='jwtuser', email='jwtuser@example.com', password='StrongPass123', role='driver'
        )

    def _get_profile(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return self.client.get(reverse('profile'))

    def test_valid_token_is_accepted(self):
        self.assertEqual(self._get_profile(_make_token(self.user.id)).status_code, 200)

    def test_expired_token_rejected(self):
        response = self._get_profile(_make_token(self.user.id, lifetime=timedelta(hours=-1)))
        self.assertEqual(response.status_code, 401)

    def test_token_without_expiry_is_rejected(self):
        response = self._get_profile(_make_token(self.user.id, drop=('exp',)))
        self.assertEqual(response.status_code, 401)

    def test_token_signed_with_other_key_rejected(self):
        response = self._get_profile(_make_token(self.user.id, key='another-key-that-is-32-characters-long!'))
        self.assertEqual(response.status_code, 401)

    def test_refresh_token_cannot_be_used_as_access_token(self):
        response = self._get_profile(_make_token(self.user.id, token_type='refresh'))
        self.assertEqual(response.status_code, 401)

    def test_token_for_deleted_user_rejected(self):
        token = _make_token(self.user.id)
        self.user.delete()
        self.assertEqual(self._get_profile(token).status_code, 401)

    def test_token_for_deactivated_user_rejected(self):
        token = _make_token(self.user.id)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self._get_profile(token).status_code, 401)

    def test_non_numeric_user_id_is_401_not_500(self):
        self.assertEqual(self._get_profile(_make_token('not-a-number')).status_code, 401)

    def test_missing_user_id_is_401_not_500(self):
        self.assertEqual(self._get_profile(_make_token(1, drop=('user_id',))).status_code, 401)

    def test_malformed_authorization_header_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token abc')
        self.assertEqual(self.client.get(reverse('profile')).status_code, 401)

    def test_role_comes_from_database_not_token_claim(self):
        token = _make_token(self.user.id, role='admin')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get(reverse('admin-user-list')).status_code, 403)


class RefreshHardeningTests(AuthTestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='refresh02', email='refresh02@example.com', password='StrongPass123', role='driver'
        )
        self.login = _login(self.client, 'refresh02').data

    def test_access_token_cannot_be_used_to_refresh(self):
        response = self.client.post(reverse('refresh'), {'refresh_token': self.login['access_token']})
        self.assertEqual(response.status_code, 401)

    def test_refresh_with_garbage_jti_is_401_not_500(self):
        token = _make_token(self.user.id, token_type='refresh', jti='not-a-uuid')
        response = self.client.post(reverse('refresh'), {'refresh_token': token})
        self.assertEqual(response.status_code, 401)

    def test_refresh_token_without_record_rejected(self):
        token = _make_token(self.user.id, token_type='refresh', jti='11111111-1111-1111-1111-111111111111')
        response = self.client.post(reverse('refresh'), {'refresh_token': token})
        self.assertEqual(response.status_code, 401)

    def test_refresh_rejected_for_deactivated_user(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.post(reverse('refresh'), {'refresh_token': self.login['refresh_token']})
        self.assertEqual(response.status_code, 401)

    def test_refresh_creates_exactly_one_new_active_token(self):
        self.client.post(reverse('refresh'), {'refresh_token': self.login['refresh_token']})
        self.assertEqual(RefreshToken.objects.filter(user=self.user, revoked=False).count(), 1)
        self.assertEqual(RefreshToken.objects.filter(user=self.user, revoked=True).count(), 1)

    def test_password_change_revokes_all_refresh_tokens(self):
        other_device = _login(self.client, 'refresh02').data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.login['access_token']}")
        response = self.client.post(reverse('change-password'), {
            'old_password': 'StrongPass123',
            'new_password': 'BrandNewPass789',
            'new_password_confirm': 'BrandNewPass789',
        })
        self.assertEqual(response.status_code, 200)
        self.client.credentials()
        for tokens_ in (self.login, other_device):
            refreshed = self.client.post(reverse('refresh'), {'refresh_token': tokens_['refresh_token']})
            self.assertEqual(refreshed.status_code, 401)

    def test_cleanup_task_removes_only_expired_tokens(self):
        now = timezone.now()
        RefreshToken.objects.create(user=self.user, issued_at=now - timedelta(days=10), expires_at=now - timedelta(days=3))
        active_before = RefreshToken.objects.filter(expires_at__gt=now).count()
        deleted = cleanup_expired_refresh_tokens()
        self.assertEqual(deleted, 1)
        self.assertEqual(RefreshToken.objects.filter(expires_at__gt=now).count(), active_before)


@override_settings(AUTH_MAX_FAILED_LOGINS=3, AUTH_LOCKOUT_SECONDS=60)
class LoginLockoutTests(AuthTestCase):

    def setUp(self):
        User.objects.create_user(username='lock01', email='lock01@example.com', password='StrongPass123')
        User.objects.create_user(username='lock02', email='lock02@example.com', password='StrongPass123')

    def test_locked_after_repeated_failures_even_with_correct_password(self):
        for _ in range(3):
            self.assertEqual(_login(self.client, 'lock01', 'wrong').status_code, 401)
        self.assertEqual(_login(self.client, 'lock01').status_code, 429)

    def test_other_accounts_are_not_affected(self):
        for _ in range(3):
            _login(self.client, 'lock01', 'wrong')
        self.assertEqual(_login(self.client, 'lock02').status_code, 200)

    def test_successful_login_resets_counter(self):
        for _ in range(2):
            _login(self.client, 'lock01', 'wrong')
        self.assertEqual(_login(self.client, 'lock01').status_code, 200)
        for _ in range(2):
            _login(self.client, 'lock01', 'wrong')
        self.assertEqual(_login(self.client, 'lock01').status_code, 200)

    def test_lockout_expires(self):
        for _ in range(3):
            _login(self.client, 'lock01', 'wrong')
        cache.clear()
        self.assertEqual(_login(self.client, 'lock01').status_code, 200)


class RegistrationHardeningTests(AuthTestCase):

    def setUp(self):
        self.url = reverse('register')
        self.payload = {
            'username': 'newdriver', 'email': 'NewDriver@Example.com',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
        }

    def test_email_is_stored_lowercase(self):
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 201)
        self.assertEqual(User.objects.get(username='newdriver').email, 'newdriver@example.com')

    def test_username_with_spaces_or_control_characters_rejected(self):
        for bad in ('bad name', 'bad\nname', 'bad<script>'):
            response = self.client.post(self.url, {**self.payload, 'username': bad})
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('username', response.data)

    def test_persian_username_is_allowed(self):
        response = self.client.post(self.url, {**self.payload, 'username': 'کاربر_۱'})
        self.assertEqual(response.status_code, 201)

    def test_overlong_password_rejected(self):
        long_password = 'Aa1' * 50
        response = self.client.post(self.url, {**self.payload, 'password': long_password, 'password_confirm': long_password})
        self.assertEqual(response.status_code, 400)

    @override_settings(ALLOW_SELF_REGISTRATION=False)
    def test_self_registration_can_be_disabled(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='newdriver').exists())

    def test_database_enforces_case_insensitive_unique_username_and_email(self):
        User.objects.create_user(username='Bob', email='bob@example.com', password='StrongPass123')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='bob', email='other@example.com', password='StrongPass123')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='bob2', email='BOB@example.com', password='StrongPass123')

    def test_duplicate_email_containing_the_word_username_reports_email(self):
        User.objects.create_user(username='u1', email='username@example.com', password='StrongPass123')
        with self.assertRaises(ValidationError) as ctx:
            AuthService.register_user({
                'username': 'u2', 'email': 'username@example.com', 'password': 'StrongPass123',
            })
        self.assertIn('email', ctx.exception.message_dict)
        self.assertNotIn('username', ctx.exception.message_dict)

    def test_superuser_gets_admin_role(self):
        root = User.objects.create_superuser(username='root', email='root@example.com', password='StrongPass123')
        self.assertEqual(root.role, 'admin')


class AdminSafetyTests(AuthTestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='adm1', email='adm1@example.com', password='StrongPass123', role='admin'
        )
        self.manager = User.objects.create_user(
            username='mgr1', email='mgr1@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.driver = User.objects.create_user(
            username='drv1', email='drv1@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('adm1')

    def _login_as(self, username):
        token = _login(self.client, username).data['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _detail(self, user_id):
        return reverse('admin-user-detail', args=[user_id])

    def test_fleet_manager_cannot_use_admin_endpoints(self):
        self._login_as('mgr1')
        self.assertEqual(self.client.get(reverse('admin-user-list')).status_code, 403)
        self.assertEqual(self.client.patch(self._detail(self.driver.id), {'is_active': False}).status_code, 403)
        self.assertEqual(self.client.delete(self._detail(self.driver.id)).status_code, 403)

    def test_unknown_role_filter_is_400(self):
        self.assertEqual(self.client.get(reverse('admin-user-list'), {'role': 'boss'}).status_code, 400)

    def test_role_filter_works(self):
        response = self.client.get(reverse('admin-user-list'), {'role': 'driver'})
        self.assertEqual([u['username'] for u in response.data], ['drv1'])

    def test_patch_unknown_user_is_404(self):
        self.assertEqual(self.client.patch(self._detail(999999), {'is_active': False}).status_code, 404)

    def test_delete_unknown_user_is_404(self):
        self.assertEqual(self.client.delete(self._detail(999999)).status_code, 404)

    def test_admin_cannot_deactivate_or_demote_self(self):
        self.assertEqual(self.client.patch(self._detail(self.admin.id), {'is_active': False}).status_code, 400)
        self.assertEqual(self.client.patch(self._detail(self.admin.id), {'role': 'driver'}).status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.role, 'admin')

    def test_admin_cannot_delete_self(self):
        self.assertEqual(self.client.delete(self._detail(self.admin.id)).status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_last_active_admin_cannot_be_deactivated_or_deleted(self):
        former_admin = User.objects.create_user(
            username='adm3', email='adm3@example.com', password='StrongPass123', role='admin', is_active=False
        )
        with self.assertRaises(DRFValidationError):
            UserService.admin_update_user(former_admin, self.admin.id, {'is_active': False})
        with self.assertRaises(DRFValidationError):
            UserService.admin_update_user(former_admin, self.admin.id, {'role': 'driver'})
        with self.assertRaises(DRFValidationError):
            UserService.delete_user(former_admin, self.admin.id)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_can_deactivate_another_admin_when_one_remains(self):
        second = User.objects.create_user(
            username='adm2', email='adm2@example.com', password='StrongPass123', role='admin'
        )
        self.assertEqual(self.client.patch(self._detail(second.id), {'is_active': False}).status_code, 200)

    def test_admin_can_still_edit_own_name(self):
        response = self.client.patch(self._detail(self.admin.id), {'first_name': 'Ali'})
        self.assertEqual(response.status_code, 200)

    def test_deactivating_a_user_revokes_their_refresh_tokens(self):
        driver_tokens = _login(self.client, 'drv1').data
        self.assertEqual(self.client.patch(self._detail(self.driver.id), {'is_active': False}).status_code, 200)
        self.assertFalse(RefreshToken.objects.filter(user=self.driver, revoked=False).exists())
        self.client.credentials()
        response = self.client.post(reverse('refresh'), {'refresh_token': driver_tokens['refresh_token']})
        self.assertEqual(response.status_code, 401)

    def test_admin_create_user_normalizes_email(self):
        response = self.client.post(reverse('admin-user-list'), {
            'username': 'newmgr', 'email': 'NewMgr@Example.com', 'role': 'fleet_manager',
            'password': 'StrongPass123', 'password_confirm': 'StrongPass123',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], 'newmgr@example.com')


class ProfileShapeTests(AuthTestCase):

    def test_profile_contains_display_fields(self):
        user = User.objects.create_user(
            username='shape01', email='shape01@example.com', password='StrongPass123',
            first_name='Ali', last_name='Rezaei',
        )
        token = _login(self.client, 'shape01').data['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        data = self.client.get(reverse('profile')).data
        self.assertEqual(data['full_name'], 'Ali Rezaei')
        self.assertEqual(data['role_display'], 'Driver')
        self.assertEqual(data['id'], user.id)
        self.assertNotIn('password', data)