from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User


class RegisterTests(APITestCase):
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


class LoginTests(APITestCase):
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


class RefreshTokenTests(APITestCase):
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


class ProfileTests(APITestCase):
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_same_as_old_password_rejected(self):
        response = self.client.post(reverse('change-password'), {
            'old_password': 'StrongPass123',
            'new_password': 'StrongPass123',
            'new_password_confirm': 'StrongPass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('StrongPass123'))


class AdminUserManagementTests(APITestCase):

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


class RegisterPrivilegeEscalationTests(APITestCase):

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


class RefreshTokenRotationTests(APITestCase):

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