from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User
from fleet_monitoring.error_utils import integrity_error_to_validation
from telemetry_module.models import TelemetryLog

from .models import Company, Driver, Vehicle
from .services import CompanyService

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM_CACHE)
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


class VehicleDataQualityTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('vehicle-list-create')
        self._login_as('admin01')

    def _payload(self, n, **extra):
        payload = {'vehicle_id': f'veh_q{n}', 'license_plate': f'12ب1{n:04d}'[:8]}
        payload.update(extra)
        return payload

    def test_empty_vin_is_stored_as_null_so_many_vehicles_can_omit_it(self):
        first = self.client.post(self.url, self._payload(1, vin=''))
        second = self.client.post(self.url, self._payload(2, vin=''))
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(Vehicle.objects.filter(vin__isnull=True).count(), 2)

    def test_model_save_normalizes_empty_vin(self):
        vehicle = Vehicle.objects.create(vehicle_id='veh_q9', license_plate='12ب99999', company=self.company, vin='')
        vehicle.refresh_from_db()
        self.assertIsNone(vehicle.vin)

    def test_vin_and_obu_serial_are_stored_upper_case(self):
        response = self.client.post(
            self.url, self._payload(3, vin='1hgcm82633a004352', obu_serial_number='obu-2026-0009')
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['vin'], '1HGCM82633A004352')
        self.assertEqual(response.data['obu']['serial_number'], 'OBU-2026-0009')

    def test_obu_serial_is_unique_regardless_of_letter_case(self):
        self.client.post(self.url, self._payload(4, obu_serial_number='OBU-2026-0100'))
        before = Vehicle.objects.count()
        response = self.client.post(self.url, self._payload(5, obu_serial_number='obu-2026-0100'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('serial_number', response.data)
        self.assertEqual(Vehicle.objects.count(), before)

    def test_invalid_obu_serial_is_reported_under_the_field_the_client_sent(self):
        response = self.client.post(self.url, self._payload(6, obu_serial_number='BAD'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('obu_serial_number', response.data)

    def test_persian_digits_and_arabic_letters_in_plate_are_normalized(self):
        response = self.client.post(self.url, {'vehicle_id': 'veh_fa1', 'license_plate': '۱۲ب۳۴۵۶۷'})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['license_plate'], '12ب34567')

    def test_year_accepts_gregorian_and_solar_hijri_but_rejects_nonsense(self):
        for n, year in enumerate((2023, 1403), start=10):
            response = self.client.post(self.url, self._payload(n, year=year))
            self.assertEqual(response.status_code, 201, (year, response.data))
        for n, year in enumerate((1800, 3000, 0), start=20):
            response = self.client.post(self.url, self._payload(n, year=year))
            self.assertEqual(response.status_code, 400, year)
            self.assertIn('year', response.data)

    def test_vehicle_id_format_is_enforced(self):
        for bad in ('bad id', 'x/y', '../etc', ''):
            response = self.client.post(self.url, {'vehicle_id': bad, 'license_plate': '12ب55555'})
            self.assertEqual(response.status_code, 400, repr(bad))
            self.assertIn('vehicle_id', response.data)

    def test_legacy_invalid_vehicle_id_does_not_block_unrelated_updates(self):
        legacy = Vehicle.objects.create(vehicle_id='legacy id!', license_plate='12ب77777', company=self.company)
        response = self.client.patch(reverse('vehicle-detail', args=[legacy.id]), {'status': 'maintenance'})
        self.assertEqual(response.status_code, 200, response.data)

    def test_unknown_vehicle_is_404_with_detail(self):
        response = self.client.get(reverse('vehicle-detail', args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertIn('Vehicle not found', str(response.data['detail']))


class IntegrityErrorMappingTests(VehicleTestBase):
    KNOWN = ('vin', 'vehicle_id', 'license_plate', 'user')

    def test_reports_the_violated_column_not_a_field_name_inside_the_value(self):
        exc = IntegrityError(
            'duplicate key value violates unique constraint "vehicles_vehicle_id_key"\n'
            'DETAIL:  Key (vehicle_id)=(my_vin_1) already exists.'
        )
        error = integrity_error_to_validation(exc, self.KNOWN)
        self.assertEqual(list(error.message_dict), ['vehicle_id'])

    def test_alias_and_custom_message(self):
        exc = IntegrityError('duplicate key ...\nDETAIL:  Key (user_id)=(5) already exists.')
        error = integrity_error_to_validation(
            exc, self.KNOWN, aliases={'user_id': 'user'}, messages={'user': 'This user already has a driver profile'},
        )
        self.assertEqual(error.message_dict, {'user': ['This user already has a driver profile']})

    def test_unknown_violation_gets_generic_message(self):
        error = integrity_error_to_validation(IntegrityError('something else'), self.KNOWN)
        self.assertIn('detail', error.message_dict)


class DriverAssignmentSecurityTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.mine = Vehicle.objects.create(
            vehicle_id='veh_mine', license_plate='12ب11111', company=self.company, assigned_manager=self.manager,
        )
        other_user = User.objects.create_user(
            username='drv_other', email='drv_other@example.com', password='StrongPass123', role='driver'
        )
        self.other_driver = Driver.objects.create(user=other_user, license_number='5555555555')
        Vehicle.objects.create(
            vehicle_id='veh_theirs', license_plate='12ب22222', company=self.company,
            assigned_manager=self.other_manager, driver=self.other_driver,
        )

    def test_manager_cannot_take_another_managers_driver_by_id(self):
        self._login_as('fm01')
        response = self.client.patch(reverse('vehicle-detail', args=[self.mine.id]), {'driver': self.other_driver.id})
        self.assertEqual(response.status_code, 403)
        self.mine.refresh_from_db()
        self.assertIsNone(self.mine.driver_id)

    def test_manager_cannot_create_a_vehicle_with_another_managers_driver(self):
        self._login_as('fm01')
        response = self.client.post(reverse('vehicle-list-create'), {
            'vehicle_id': 'veh_new', 'license_plate': '12ب33334', 'driver': self.other_driver.id,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Vehicle.objects.filter(vehicle_id='veh_new').exists())

    def test_manager_can_assign_an_unassigned_driver(self):
        self._login_as('fm01')
        response = self.client.patch(reverse('vehicle-detail', args=[self.mine.id]), {'driver': self.driver.id})
        self.assertEqual(response.status_code, 200, response.data)

    def test_admin_can_assign_any_driver(self):
        self._login_as('admin01')
        response = self.client.patch(reverse('vehicle-detail', args=[self.mine.id]), {'driver': self.other_driver.id})
        self.assertEqual(response.status_code, 200, response.data)

    def test_inactive_driver_cannot_be_assigned(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._login_as('admin01')
        response = self.client.patch(reverse('vehicle-detail', args=[self.mine.id]), {'driver': self.driver.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('driver', response.data)

    def test_deactivated_driver_loses_access_to_vehicle(self):
        Vehicle.objects.filter(pk=self.mine.pk).update(driver=self.driver)
        self._login_as('drv01')
        self.assertEqual(len(self.client.get(reverse('vehicle-me')).data), 1)
        self.assertEqual(self.client.get(reverse('vehicle-status', args=[self.mine.id])).status_code, 200)

        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse('vehicle-me')).data, [])
        self.assertEqual(self.client.get(reverse('vehicle-status', args=[self.mine.id])).status_code, 403)


class VehicleDeleteGuardTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(vehicle_id='veh_del', license_plate='12ب44444', company=self.company)
        self._login_as('admin01')

    def test_vehicle_with_telemetry_cannot_be_deleted(self):
        TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp=timezone.now(), speed=1, engine_temperature=1,
            battery_voltage=1, fuel_level=1, latitude=1, longitude=1, odometer=1, raw_payload={},
        )
        response = self.client.delete(reverse('vehicle-detail', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('decommissioned', str(response.data['detail']))
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_vehicle_without_history_can_still_be_deleted(self):
        response = self.client.delete(reverse('vehicle-detail', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, 204)

    def test_decommissioning_keeps_history(self):
        response = self.client.patch(reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'decommissioned'})
        self.assertEqual(response.status_code, 200)


class DashboardCacheInvalidationTests(VehicleTestBase):
    def _stats(self, username):
        self._login_as(username)
        return self.client.get(reverse('vehicle-dashboard-stats')).data

    def test_creating_a_vehicle_refreshes_admin_and_manager_dashboards(self):
        self.assertEqual(self._stats('fm01')['total_vehicles'], 0)
        self.assertEqual(self._stats('admin01')['total_vehicles'], 0)

        self._login_as('admin01')
        response = self.client.post(reverse('vehicle-list-create'), {
            'vehicle_id': 'veh_dc1', 'license_plate': '12ب66661', 'assigned_manager': self.manager.id,
        })
        self.assertEqual(response.status_code, 201, response.data)

        self.assertEqual(self._stats('admin01')['total_vehicles'], 1)
        self.assertEqual(self._stats('fm01')['total_vehicles'], 1)

    def test_reassignment_refreshes_both_managers(self):
        vehicle = Vehicle.objects.create(
            vehicle_id='veh_dc2', license_plate='12ب66662', company=self.company, assigned_manager=self.manager,
        )
        self.assertEqual(self._stats('fm01')['total_vehicles'], 1)
        self.assertEqual(self._stats('fm02')['total_vehicles'], 0)

        self._login_as('admin01')
        self.client.patch(reverse('vehicle-detail', args=[vehicle.id]), {'assigned_manager': self.other_manager.id})

        self.assertEqual(self._stats('fm01')['total_vehicles'], 0)
        self.assertEqual(self._stats('fm02')['total_vehicles'], 1)

    def test_total_equals_sum_of_statuses(self):
        for n, state in enumerate(('active', 'active', 'inactive')):
            Vehicle.objects.create(
                vehicle_id=f'veh_s{n}', license_plate=f'12ب7770{n}', company=self.company, status=state,
            )
        data = self._stats('admin01')
        self.assertEqual(data['total_vehicles'], sum(data['vehicles_by_status'].values()))
        self.assertEqual(data['vehicles_by_status']['active'], 2)


class VehicleListFilterAndPaginationTests(VehicleTestBase):
    def setUp(self):
        super().setUp()
        for n in range(5):
            Vehicle.objects.create(
                vehicle_id=f'veh_f{n}', license_plate=f'12ب1000{n}', company=self.company,
                make='Ford' if n % 2 else 'Volvo', status='active' if n < 3 else 'maintenance',
                assigned_manager=self.manager if n < 4 else self.other_manager,
            )
        self.url = reverse('vehicle-list-create')
        self._login_as('admin01')

    def test_default_response_is_a_plain_array(self):
        response = self.client.get(self.url)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 5)

    def test_filter_by_status(self):
        response = self.client.get(self.url, {'status': 'maintenance'})
        self.assertEqual(len(response.data), 2)

    def test_invalid_status_filter_is_400(self):
        self.assertEqual(self.client.get(self.url, {'status': 'flying'}).status_code, 400)

    def test_search_matches_plate_even_with_persian_digits(self):
        response = self.client.get(self.url, {'search': '۱۰۰۰۲'})
        self.assertEqual([v['vehicle_id'] for v in response.data], ['veh_f2'])

    def test_search_matches_make(self):
        self.assertEqual(len(self.client.get(self.url, {'search': 'volvo'}).data), 3)

    def test_manager_filter_is_admin_only(self):
        self._login_as('fm01')
        response = self.client.get(self.url, {'assigned_manager': self.other_manager.id})
        self.assertEqual(len(response.data), 4)

    def test_admin_can_filter_by_manager(self):
        response = self.client.get(self.url, {'assigned_manager': self.other_manager.id})
        self.assertEqual([v['vehicle_id'] for v in response.data], ['veh_f4'])

    def test_opt_in_pagination_envelope(self):
        response = self.client.get(self.url, {'page_size': 2})
        self.assertEqual(response.data['count'], 5)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNotNone(response.data['next'])

    def test_pagination_has_stable_order_with_no_duplicates_across_pages(self):
        seen = []
        for page in (1, 2, 3):
            seen += [v['id'] for v in self.client.get(self.url, {'page': page, 'page_size': 2}).data['results']]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 5)

    def test_driver_list_search(self):
        response = self.client.get(reverse('driver-list-create'), {'search': 'drv01'})
        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_list_is_401(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)


class DriverConstraintTests(VehicleTestBase):
    def _driver(self, n, phone=''):
        user = User.objects.create_user(
            username=f'dc{n}', email=f'dc{n}@example.com', password='StrongPass123', role='driver'
        )
        return Driver.objects.create(user=user, license_number=f'90000000{n:02d}', phone_number=phone)

    def test_database_rejects_a_shared_phone_number(self):
        self._driver(1, '09120000001')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._driver(2, '09120000001')

    def test_database_allows_many_blank_phone_numbers(self):
        self._driver(3)
        self._driver(4)
        self.assertEqual(Driver.objects.filter(phone_number='').count(), 3)

    def test_api_reports_phone_conflict_under_phone_number(self):
        self._driver(5, '09120000005')
        user = User.objects.create_user(username='dc6', email='dc6@example.com', password='StrongPass123', role='driver')
        self._login_as('admin01')
        response = self.client.post(reverse('driver-list-create'), {
            'user': user.id, 'license_number': '9000000006', 'phone_number': '۰۹۱۲۰۰۰۰۰۰۵',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['phone_number'], ['phone_number already exists'])

    def test_persian_digits_in_driver_fields_are_normalized(self):
        user = User.objects.create_user(username='dc7', email='dc7@example.com', password='StrongPass123', role='driver')
        self._login_as('admin01')
        response = self.client.post(reverse('driver-list-create'), {
            'user': user.id, 'license_number': '۹۰۰۰۰۰۰۰۰۷', 'phone_number': '۰۹۱۲۰۰۰۰۰۰۷',
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['license_number'], '9000000007')
        self.assertEqual(response.data['phone_number'], '09120000007')


class CompanyServiceTests(VehicleTestBase):
    def test_get_company_is_deterministic_oldest_first(self):
        Company.objects.all().delete()
        oldest = Company.objects.create(name='Oldest Company')
        Company.objects.create(name='Zzz Later Company')
        self.assertEqual(CompanyService.get_company().pk, oldest.pk)


class DriverDeactivateAndRoleChangeTests(VehicleTestBase):
    def _driver(self, n, phone=''):
        user = User.objects.create_user(
            username=f'rc{n}', email=f'rc{n}@example.com', password='StrongPass123', role='driver'
        )
        driver = Driver.objects.create(user=user, license_number=f'80000000{n:02d}', phone_number=phone)
        return user, driver

    def test_deactivating_driver_with_unchanged_phone_succeeds(self):
        _, driver = self._driver(1, '09121111111')
        self._login_as('admin01')
        response = self.client.patch(reverse('driver-detail', args=[driver.id]), {
            'license_number': driver.license_number, 'phone_number': '09121111111', 'is_active': False,
        })
        self.assertEqual(response.status_code, 200, response.data)
        driver.refresh_from_db()
        self.assertFalse(driver.is_active)

    def test_changing_phone_to_another_drivers_phone_is_still_rejected(self):
        self._driver(2, '09122222222')
        _, other = self._driver(3, '09123333333')
        self._login_as('admin01')
        response = self.client.patch(
            reverse('driver-detail', args=[other.id]), {'phone_number': '09122222222'}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone_number', response.data)

    def test_role_change_deletes_driver_profile_and_unassigns_vehicles(self):
        user, driver = self._driver(4, '09124444444')
        vehicle = Vehicle.objects.create(
            vehicle_id='veh_rc4', company=self.company, license_plate='12ب34568', driver=driver,
        )
        self._login_as('admin01')
        response = self.client.patch(reverse('admin-user-detail', args=[user.id]), {'role': 'fleet_manager'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Driver.objects.filter(pk=driver.pk).exists())
        vehicle.refresh_from_db()
        self.assertIsNone(vehicle.driver_id)

    def test_user_can_get_a_fresh_driver_profile_after_returning_to_driver_role(self):
        user, _ = self._driver(5, '09125555555')
        self._login_as('admin01')
        self.client.patch(reverse('admin-user-detail', args=[user.id]), {'role': 'fleet_manager'})
        self.client.patch(reverse('admin-user-detail', args=[user.id]), {'role': 'driver'})
        response = self.client.post(reverse('driver-list-create'), {
            'user': user.id, 'license_number': '8000000005', 'phone_number': '09125555555',
        })
        self.assertEqual(response.status_code, 201, response.data)

    def test_deactivating_driver_account_keeps_profile_but_marks_inactive(self):
        user, driver = self._driver(6)
        self._login_as('admin01')
        response = self.client.patch(reverse('admin-user-detail', args=[user.id]), {'is_active': False})
        self.assertEqual(response.status_code, 200, response.data)
        driver.refresh_from_db()
        self.assertFalse(driver.is_active)