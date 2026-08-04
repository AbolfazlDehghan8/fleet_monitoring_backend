from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager, IsDriver
from .serializers import (
    DriverCreateSerializer,
    DriverSerializer,
    DriverUpdateSerializer,
    VehicleAdminUpdateSerializer,
    VehicleCreateSerializer,
    VehicleManagerUpdateSerializer,
    VehicleSerializer,
)
from .services import DriverService, VehicleService


def _error_response(exc):

    if isinstance(exc, PermissionDenied):
        return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    detail = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
    is_not_found = detail.get('detail') in ('Vehicle not found', 'Driver not found')
    status_code = status.HTTP_404_NOT_FOUND if is_not_found else status.HTTP_400_BAD_REQUEST
    return Response(detail, status=status_code)


class VehicleListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: VehicleSerializer(many=True)},
        summary='List vehicles',
        description='Admin sees all vehicles; Fleet Manager sees only vehicles assigned to them.',
    )
    def get(self, request):
        vehicles = VehicleService.list_vehicles(request.user)
        return Response(VehicleSerializer(vehicles, many=True).data, status=status.HTTP_200_OK)

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

        try:
            vehicle = VehicleService.create_vehicle(request.user, serializer.validated_data)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_201_CREATED)


class VehicleDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: VehicleSerializer, 403: 'Forbidden', 404: 'Not Found'},
        summary='Retrieve a vehicle by id',
    )
    def get(self, request, vehicle_id):
        try:
            vehicle = VehicleService.get_vehicle_for_user(request.user, vehicle_id)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

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
            VehicleAdminUpdateSerializer if request.user.role == 'admin' else VehicleManagerUpdateSerializer
        )
        serializer = serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            vehicle = VehicleService.update_vehicle(request.user, vehicle_id, serializer.validated_data)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None, 403: 'Forbidden', 404: 'Not Found'},
        summary='Delete a vehicle (admin only)',
    )
    def delete(self, request, vehicle_id):
        try:
            VehicleService.delete_vehicle(request.user, vehicle_id)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleStatusView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: 'Success', 403: 'Forbidden', 404: 'Not Found'},
        summary='Get cached vehicle status',
    )
    def get(self, request, vehicle_id):
        try:
            payload = VehicleService.get_vehicle_status(request.user, vehicle_id)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(payload, status=status.HTTP_200_OK)


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
        responses={200: DriverSerializer(many=True)},
        summary='List driver profiles',
        description='Admin sees all drivers; Fleet Manager sees only drivers assigned to their vehicles.',
    )
    def get(self, request):
        try:
            drivers = DriverService.list_drivers(request.user)
        except PermissionDenied as exc:
            return _error_response(exc)
        return Response(DriverSerializer(drivers, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=DriverCreateSerializer,
        responses={201: DriverSerializer, 400: 'Bad Request'},
        summary='Create a driver profile',
        description='Links an existing user (role=driver) to a driver profile.',
    )
    def post(self, request):
        serializer = DriverCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            driver = DriverService.create_driver(request.user, serializer.validated_data)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)


class DriverDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(responses={200: DriverSerializer, 404: 'Not Found'}, summary='Retrieve a driver')
    def get(self, request, driver_id):
        try:
            driver = DriverService.get_driver(request.user, driver_id)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)
        return Response(DriverSerializer(driver).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=DriverUpdateSerializer,
        responses={200: DriverSerializer, 400: 'Bad Request', 404: 'Not Found'},
        summary='Update a driver profile',
    )
    def patch(self, request, driver_id):
        serializer = DriverUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            driver = DriverService.update_driver(request.user, driver_id, serializer.validated_data)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(DriverSerializer(driver).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 403: 'Forbidden', 404: 'Not Found'}, summary='Delete a driver profile')
    def delete(self, request, driver_id):
        try:
            DriverService.delete_driver(request.user, driver_id)
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)
