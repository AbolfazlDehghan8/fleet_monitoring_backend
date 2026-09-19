from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User

from .models import Company, Driver, Vehicle


class VehicleTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name='Test Company')
        self.admin = User.objects.create_user(
            username='admin01', email='admin01@example.com', password='StrongPass123', role='admin'
        )
        self.manager = User.objects.create_user(
            username='fm01', email='fm01@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.other_manager = User.objects.create_user(
            username='fm02', email='fm02@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.driver_user = User.objects.create_user(
            username='drv01', email='drv01@example.com', password='StrongPass123', role='driver'
        )
        self.driver = Driver.objects.create(user=self.driver_user, license_number='DL-001')

    def _login_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class VehicleCreateTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('vehicle-list-create')
        self.payload = {
            'vehicle_id': 'veh_0001',
            'license_plate': '12ب34567',
            'vin': '1HGCM82633A004352',
            'make': 'Ford',
            'model': 'Transit',
            'year': 2023,
            'obu_serial_number': 'OBU-2026-0001',
        }

    def test_admin_can_create_vehicle(self):
        self._login_as('admin01')
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(response.data['obu']['serial_number'], 'OBU-2026-0001')

    def test_fleet_manager_can_create_vehicle_auto_assigned_to_self(self):
        self._login_as('fm01')
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assigned_manager'], self.manager.id)

    def test_driver_cannot_create_vehicle(self):
        self._login_as('drv01')
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_license_plate_rejected(self):
        self._login_as('admin01')
        self.client.post(self.url, self.payload)
        self.payload['vehicle_id'] = 'veh_0002'
        self.payload['vin'] = '1HGCM82633A004353'
        self.payload['obu_serial_number'] = 'OBU-2026-0002'
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VehicleListRetrieveTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.vehicle_a = Vehicle.objects.create(
            vehicle_id='veh_a', license_plate='12ب11111', company=self.company,
            make='Ford', model='Transit', assigned_manager=self.manager,
        )
        self.vehicle_b = Vehicle.objects.create(
            vehicle_id='veh_b', license_plate='12ب22222', company=self.company,
            make='Ford', model='Transit', assigned_manager=self.other_manager,
        )

    def test_admin_sees_all_vehicles(self):
        self._login_as('admin01')
        response = self.client.get(reverse('vehicle-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_fleet_manager_sees_only_assigned_vehicles(self):
        self._login_as('fm01')
        response = self.client.get(reverse('vehicle-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.vehicle_a.id)

    def test_driver_cannot_list_vehicles(self):
        self._login_as('drv01')
        response = self.client.get(reverse('vehicle-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fleet_manager_cannot_retrieve_unassigned_vehicle(self):
        self._login_as('fm01')
        response = self.client.get(reverse('vehicle-detail', args=[self.vehicle_b.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_retrieve_any_vehicle(self):
        self._login_as('admin01')
        response = self.client.get(reverse('vehicle-detail', args=[self.vehicle_b.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class VehicleUpdateDeleteTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_c', license_plate='12ب33333', company=self.company,
            make='Ford', model='Transit', assigned_manager=self.manager,
        )

    def test_admin_can_update_any_field_including_reassignment(self):
        self._login_as('admin01')
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.id]),
            {'make': 'Volvo', 'assigned_manager': self.other_manager.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['make'], 'Volvo')
        self.assertEqual(response.data['assigned_manager'], self.other_manager.id)

    def test_assigned_manager_can_update_status(self):
        self._login_as('fm01')
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'maintenance'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'maintenance')

    def test_assigned_manager_cannot_reassign_to_another_manager(self):
        self._login_as('fm01')
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.id]),
            {'assigned_manager': self.other_manager.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.assigned_manager_id, self.manager.id)

    def test_unassigned_manager_cannot_update(self):
        self._login_as('fm02')
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'maintenance'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fleet_manager_cannot_delete_vehicle(self):
        self._login_as('fm01')
        response = self.client.delete(reverse('vehicle-detail', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_vehicle(self):
        self._login_as('admin01')
        response = self.client.delete(reverse('vehicle-detail', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Vehicle.objects.filter(id=self.vehicle.id).exists())


class VehicleMeAndStatusTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_d', license_plate='12ب44444', company=self.company,
            make='Ford', model='Transit', assigned_manager=self.manager, driver=self.driver,
        )

    def test_driver_can_get_own_vehicle(self):
        self._login_as('drv01')
        response = self.client.get(reverse('vehicle-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.vehicle.id)

    def test_driver_without_profile_gets_empty_list(self):
        User.objects.create_user(
            username='drv02', email='drv02@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('drv02')
        response = self.client.get(reverse('vehicle-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_admin_cannot_use_me_endpoint(self):
        self._login_as('admin01')
        response = self.client.get(reverse('vehicle-me'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_endpoint_accessible_to_assigned_driver(self):
        self._login_as('drv01')
        response = self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')

    def test_status_endpoint_denied_for_unrelated_driver(self):
        other_driver_user = User.objects.create_user(
            username='drv03', email='drv03@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=other_driver_user, license_number='DL-002')
        self._login_as('drv03')
        response = self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_endpoint_is_cached_between_requests(self):
        self._login_as('admin01')
        first = self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        Vehicle.objects.filter(id=self.vehicle.id).update(status='maintenance')

        second = self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))
        self.assertEqual(second.data['status'], 'active')

    def test_update_invalidates_status_cache(self):
        self._login_as('admin01')
        self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))

        self.client.patch(reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'maintenance'})

        response = self.client.get(reverse('vehicle-status', args=[self.vehicle.id]))
        self.assertEqual(response.data['status'], 'maintenance')


class DriverEndpointTests(VehicleTestBase):
    def test_admin_can_create_driver_profile(self):
        new_user = User.objects.create_user(
            username='drv09', email='drv09@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('admin01')
        response = self.client.post(
            reverse('driver-list-create'), {'user': new_user.id, 'license_number': '1234509909'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_license_number_format_rejected(self):
        new_user = User.objects.create_user(
            username='drv15', email='drv15@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('admin01')
        response = self.client.post(
            reverse('driver-list-create'), {'user': new_user.id, 'license_number': 'DL-099'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('license_number', response.data)

    def test_duplicate_phone_number_rejected(self):
        first_user = User.objects.create_user(
            username='drv16', email='drv16@example.com', password='StrongPass123', role='driver'
        )
        second_user = User.objects.create_user(
            username='drv17', email='drv17@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('admin01')
        first = self.client.post(
            reverse('driver-list-create'),
            {'user': first_user.id, 'license_number': '1111111111', 'phone_number': '09123456789'},
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            reverse('driver-list-create'),
            {'user': second_user.id, 'license_number': '2222222222', 'phone_number': '09123456789'},
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', second.data)

    def test_two_drivers_can_both_leave_phone_number_blank(self):
        first_user = User.objects.create_user(
            username='drv18', email='drv18@example.com', password='StrongPass123', role='driver'
        )
        second_user = User.objects.create_user(
            username='drv19', email='drv19@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('admin01')
        first = self.client.post(
            reverse('driver-list-create'), {'user': first_user.id, 'license_number': '3333333333'}
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            reverse('driver-list-create'), {'user': second_user.id, 'license_number': '4444444444'}
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

    def test_duplicate_license_number_rejected_on_update(self):
        first_user = User.objects.create_user(
            username='drv20', email='drv20@example.com', password='StrongPass123', role='driver'
        )
        second_user = User.objects.create_user(
            username='drv21', email='drv21@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=first_user, license_number='5555555555')
        other_driver = Driver.objects.create(user=second_user, license_number='6666666666')
        self._login_as('admin01')

        response = self.client.patch(
            reverse('driver-detail', args=[other_driver.id]), {'license_number': '5555555555'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('license_number', response.data)
        self.assertEqual(response.data['license_number'], ['license_number already exists'])

    def test_fleet_manager_sees_only_drivers_of_their_vehicles(self):
        Vehicle.objects.create(
            vehicle_id='veh_e', license_plate='12ب55555', company=self.company,
            assigned_manager=self.manager, driver=self.driver,
        )
        other_driver_user = User.objects.create_user(
            username='drv04', email='drv04@example.com', password='StrongPass123', role='driver'
        )
        other_driver = Driver.objects.create(user=other_driver_user, license_number='DL-003')
        Vehicle.objects.create(
            vehicle_id='veh_f', license_plate='12ب66666', company=self.company,
            assigned_manager=self.other_manager, driver=other_driver,
        )

        self._login_as('fm01')
        response = self.client.get(reverse('driver-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.driver.id)

    def test_driver_role_cannot_access_driver_list(self):
        self._login_as('drv01')
        response = self.client.get(reverse('driver-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DriverLinkableUsersTests(VehicleTestBase):
    def test_fleet_manager_sees_unlinked_driver_users_only(self):
        unlinked = User.objects.create_user(
            username='drv10', email='drv10@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('fm01')
        response = self.client.get(reverse('driver-linkable-users'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row['id'] for row in response.data}
        self.assertIn(unlinked.id, returned_ids)
        self.assertNotIn(self.driver_user.id, returned_ids)

    def test_admin_sees_unlinked_driver_users(self):
        unlinked = User.objects.create_user(
            username='drv11', email='drv11@example.com', password='StrongPass123', role='driver'
        )
        self._login_as('admin01')
        response = self.client.get(reverse('driver-linkable-users'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(unlinked.id, {row['id'] for row in response.data})

    def test_driver_cannot_access_linkable_users(self):
        self._login_as('drv01')
        response = self.client.get(reverse('driver-linkable-users'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DriverAssignableListTests(VehicleTestBase):
    def test_fleet_manager_sees_own_plus_unassigned_drivers(self):
        Vehicle.objects.create(
            vehicle_id='veh_g', license_plate='12ب77777', company=self.company,
            assigned_manager=self.manager, driver=self.driver,
        )
        free_user = User.objects.create_user(
            username='drv12', email='drv12@example.com', password='StrongPass123', role='driver'
        )
        free_driver = Driver.objects.create(user=free_user, license_number='DL-012')
        other_user = User.objects.create_user(
            username='drv13', email='drv13@example.com', password='StrongPass123', role='driver'
        )
        other_driver = Driver.objects.create(user=other_user, license_number='DL-013')
        Vehicle.objects.create(
            vehicle_id='veh_h', license_plate='12ب88888', company=self.company,
            assigned_manager=self.other_manager, driver=other_driver,
        )

        self._login_as('fm01')
        response = self.client.get(reverse('driver-assignable-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row['id'] for row in response.data}
        self.assertEqual(returned_ids, {self.driver.id, free_driver.id})

    def test_admin_sees_all_drivers_including_unassigned(self):
        free_user = User.objects.create_user(
            username='drv14', email='drv14@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=free_user, license_number='DL-014')

        self._login_as('admin01')
        response = self.client.get(reverse('driver-assignable-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), Driver.objects.count())

    def test_driver_role_cannot_access_assignable_list(self):
        self._login_as('drv01')
        response = self.client.get(reverse('driver-assignable-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DashboardStatsTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_dash_1', license_plate='12ب99999', company=self.company,
            assigned_manager=self.manager, driver=self.driver, status='active',
        )
        Vehicle.objects.create(
            vehicle_id='veh_dash_2', license_plate='12ب10101', company=self.company,
            assigned_manager=self.other_manager, status='maintenance',
        )

    def test_admin_sees_fleet_wide_stats(self):
        self._login_as('admin01')
        response = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_vehicles'], 2)
        self.assertIn('vehicles_by_status', response.data)
        self.assertIn('unacknowledged_alerts', response.data)

    def test_fleet_manager_sees_only_their_vehicles(self):
        self._login_as('fm01')
        response = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_vehicles'], 1)

    def test_driver_cannot_access_dashboard_stats(self):
        self._login_as('drv01')
        response = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stats_are_cached_until_a_vehicle_write_invalidates_them(self):
        self._login_as('admin01')
        first = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(first.data['total_vehicles'], 2)

        Vehicle.objects.create(
            vehicle_id='veh_dash_3', license_plate='12ب20202', company=self.company,
        )

        cached = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(cached.data['total_vehicles'], 2)

        self.client.patch(reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'inactive'})

        refreshed = self.client.get(reverse('vehicle-dashboard-stats'))
        self.assertEqual(refreshed.data['total_vehicles'], 3)


class CompanyViewTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('company-detail')

    def test_admin_can_retrieve_company(self):
        self._login_as('admin01')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('name', response.data)

    def test_fleet_manager_cannot_retrieve_company(self):
        self._login_as('fm01')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_cannot_retrieve_company(self):
        self._login_as('drv01')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_retrieve_company(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_update_company(self):
        self._login_as('admin01')
        response = self.client.patch(self.url, {'contact_email': 'newops@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contact_email'], 'newops@example.com')

    def test_partial_update_does_not_touch_other_fields(self):
        original_name = Company.objects.first().name
        self._login_as('admin01')
        response = self.client.patch(self.url, {'contact_phone': '02187654321'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], original_name)
        self.assertEqual(response.data['contact_phone'], '02187654321')

    def test_fleet_manager_cannot_update_company(self):
        self._login_as('fm01')
        response = self.client.patch(self.url, {'name': 'Hacked Co'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_cannot_update_company(self):
        self._login_as('drv01')
        response = self.client.patch(self.url, {'name': 'Hacked Co'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_returns_404_when_no_company_exists(self):
        Company.objects.all().delete()
        self._login_as('admin01')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_returns_404_when_no_company_exists(self):
        Company.objects.all().delete()
        self._login_as('admin01')
        response = self.client.patch(self.url, {'contact_email': 'x@example.com'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)