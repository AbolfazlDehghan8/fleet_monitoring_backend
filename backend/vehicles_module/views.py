from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdmin, IsAdminOrFleetManager, IsDriver
from fleet_monitoring.pagination import list_response

from .serializers import (
    CompanySerializer,
    CompanyUpdateSerializer,
    DriverCreateSerializer,
    DriverFilterSerializer,
    DriverSerializer,
    DriverUpdateSerializer,
    LinkableUserSerializer,
    VehicleAdminUpdateSerializer,
    VehicleCreateSerializer,
    VehicleFilterSerializer,
    VehicleManagerUpdateSerializer,
    VehicleSerializer,
)
from .services import CompanyService, DriverService, VehicleService

PAGINATION_PARAMS = [
    OpenApiParameter('page', int, description='Opt in to pagination ({count,next,previous,results}). '
                                              'Without page/page_size a plain array is returned.'),
    OpenApiParameter('page_size', int, description='Items per page (default 50, max 200).'),
]


class VehicleListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('search', str, description='Search vehicle_id, plate, VIN, make, model'),
            OpenApiParameter('driver', int, description='Filter by driver id'),
            OpenApiParameter('assigned_manager', int, description='Filter by manager id (admin only)'),
            *PAGINATION_PARAMS,
        ],
        responses={200: VehicleSerializer(many=True)},
        summary='List vehicles',
        description='Admin sees all vehicles; Fleet Manager sees only vehicles assigned to them.',
    )
    def get(self, request):
        filters = VehicleFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        vehicles = VehicleService.list_vehicles(request.user, filters.validated_data)
        return list_response(request, vehicles, VehicleSerializer)

    @extend_schema(
        request=VehicleCreateSerializer,
        responses={201: VehicleSerializer, 400: 'Bad Request'},
        summary='Create a vehicle',
        description='Admin can assign to any Fleet Manager; a Fleet Manager creating a '
                    'vehicle is auto-assigned to themself.',
    )
    def post(self, request):
        serializer = VehicleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = VehicleService.create_vehicle(request.user, serializer.validated_data)
        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_201_CREATED)


class VehicleDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: VehicleSerializer, 403: 'Forbidden', 404: 'Not Found'},
        summary='Retrieve a vehicle by id',
    )
    def get(self, request, vehicle_id):
        vehicle = VehicleService.get_vehicle_for_user(request.user, vehicle_id)
        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=VehicleAdminUpdateSerializer,
        responses={200: VehicleSerializer, 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found'},
        summary='Update a vehicle',
        description='Admin can update any field, including reassignment. Fleet Manager can '
                    'update any field on vehicles assigned to them EXCEPT `assigned_manager`.',
    )
    def patch(self, request, vehicle_id):
        serializer_class = (
            VehicleAdminUpdateSerializer if request.user.is_admin else VehicleManagerUpdateSerializer
        )
        serializer = serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vehicle = VehicleService.update_vehicle(request.user, vehicle_id, serializer.validated_data)
        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None, 400: 'Vehicle has history', 403: 'Forbidden', 404: 'Not Found'},
        summary='Delete a vehicle (admin only)',
        description='Refused (400) when the vehicle has telemetry or alerts: set its status to '
                    '`decommissioned` instead so history is preserved.',
    )
    def delete(self, request, vehicle_id):
        VehicleService.delete_vehicle(request.user, vehicle_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleStatusView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: 'Success', 403: 'Forbidden', 404: 'Not Found'},
        summary='Get cached vehicle status',
    )
    def get(self, request, vehicle_id):
        payload = VehicleService.get_vehicle_status(request.user, vehicle_id)
        return Response(payload, status=status.HTTP_200_OK)


class DashboardStatsView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: 'Success', 403: 'Forbidden'},
        summary='Get cached fleet dashboard statistics',
        description='Admin sees fleet-wide counters; Fleet Manager sees counters for their own vehicles only.',
    )
    def get(self, request):
        return Response(VehicleService.get_dashboard_stats(request.user), status=status.HTTP_200_OK)


class VehicleMeView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(
        responses={200: VehicleSerializer(many=True)},
        summary="Get the authenticated driver's own vehicle(s)",
    )
    def get(self, request):
        vehicles = VehicleService.get_vehicles_for_driver(request.user)
        return Response(VehicleSerializer(vehicles, many=True).data, status=status.HTTP_200_OK)


class DriverListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        parameters=[OpenApiParameter('search', str, description='Search license, phone, username, name'),
                    *PAGINATION_PARAMS],
        responses={200: DriverSerializer(many=True)},
        summary='List driver profiles',
        description='Admin sees all drivers; Fleet Manager sees only drivers assigned to their vehicles.',
    )
    def get(self, request):
        filters = DriverFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        drivers = DriverService.list_drivers(request.user, filters.validated_data.get('search'))
        return list_response(request, drivers, DriverSerializer)

    @extend_schema(
        request=DriverCreateSerializer,
        responses={201: DriverSerializer, 400: 'Bad Request'},
        summary='Create a driver profile',
        description='Links an existing user (role=driver) to a driver profile.',
    )
    def post(self, request):
        serializer = DriverCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        driver = DriverService.create_driver(request.user, serializer.validated_data)
        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)


class DriverLinkableUsersView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: LinkableUserSerializer(many=True)},
        summary='List driver-role users with no driver profile yet',
        description=(
            'Admin and Fleet Manager only. Narrow, read-only lookup used to populate the '
            '"linked user" picker on the driver-profile creation form. Does NOT expose '
            'general user management — that stays admin-only at /api/v1/admin/users/.'
        ),
    )
    def get(self, request):
        users = DriverService.list_linkable_users(request.user)
        return Response(LinkableUserSerializer(users, many=True).data, status=status.HTTP_200_OK)


class DriverAssignableListView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: DriverSerializer(many=True)},
        summary='List drivers eligible for assignment to a vehicle',
        description=(
            'Admin sees all drivers. Fleet Manager sees drivers already assigned to one of '
            'their vehicles PLUS drivers not yet linked to any vehicle, so a freshly created '
            'driver profile can be selected in the vehicle-assignment dropdown. The same rule '
            'is enforced when a vehicle is created/updated.'
        ),
    )
    def get(self, request):
        drivers = DriverService.list_assignable(request.user)
        return Response(DriverSerializer(drivers, many=True).data, status=status.HTTP_200_OK)


class DriverDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(responses={200: DriverSerializer, 404: 'Not Found'}, summary='Retrieve a driver')
    def get(self, request, driver_id):
        driver = DriverService.get_driver(request.user, driver_id)
        return Response(DriverSerializer(driver).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=DriverUpdateSerializer,
        responses={200: DriverSerializer, 400: 'Bad Request', 404: 'Not Found'},
        summary='Update a driver profile',
    )
    def patch(self, request, driver_id):
        serializer = DriverUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        driver = DriverService.update_driver(request.user, driver_id, serializer.validated_data)
        return Response(DriverSerializer(driver).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 403: 'Forbidden', 404: 'Not Found'}, summary='Delete a driver profile')
    def delete(self, request, driver_id):
        DriverService.delete_driver(request.user, driver_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        responses={200: CompanySerializer, 403: 'Forbidden', 404: 'Not Found'},
        summary='Retrieve company information (admin only)',
        description='Single-tenant deployment: returns the one Company record for this system.',
    )
    def get(self, request):
        return Response(CompanySerializer(CompanyService.get_company()).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=CompanyUpdateSerializer,
        responses={200: CompanySerializer, 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found'},
        summary='Update company information (admin only)',
    )
    def patch(self, request):
        serializer = CompanyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        company = CompanyService.update_company(request.user, serializer.validated_data)
        return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)