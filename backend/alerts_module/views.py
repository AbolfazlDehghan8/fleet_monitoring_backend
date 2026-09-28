from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager, IsDriver

from .serializers import AcknowledgeOwnAlertSerializer, AlertSerializer
from .services import AlertService


class AlertListView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: AlertSerializer(many=True)},
        summary='List alerts',
        description='Admin sees all alerts; Fleet Manager sees alerts for assigned vehicles',
    )
    def get(self, request):
        alerts = AlertService.list_alerts(request.user)
        return Response(AlertSerializer(alerts, many=True).data, status=status.HTTP_200_OK)


class AlertMeView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(responses={200: AlertSerializer(many=True)}, summary="Get the driver's own vehicle alerts")
    def get(self, request):
        alerts = AlertService.list_alerts_for_driver(request.user)
        return Response(AlertSerializer(alerts, many=True).data, status=status.HTTP_200_OK)


class AlertDetailView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AlertSerializer, 403: 'Forbidden', 404: 'Not Found'}, summary='Retrieve an alert')
    def get(self, request, alert_id):
        alert = AlertService.get_alert(request.user, alert_id)
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None, 403: 'Forbidden', 404: 'Not Found'},
        summary='Remove an alert from my list',
        description=(
            'Hides the alert from the caller\'s own lists only; the alert is kept and remains '
            'visible to other users. Idempotent.'
        ),
    )
    def delete(self, request, alert_id):
        AlertService.dismiss(request.user, alert_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlertAcknowledgeView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: AlertSerializer, 403: 'Forbidden', 404: 'Not Found'},
        summary='Acknowledge an alert',
        description='Idempotent: acknowledging an already-acknowledged alert is a no-op that still returns 200',
    )
    def post(self, request, alert_id):
        alert = AlertService.acknowledge(request.user, alert_id)
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)


class AlertMeAcknowledgeView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(
        request=AcknowledgeOwnAlertSerializer,
        responses={200: AlertSerializer, 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found'},
        summary="Acknowledge one of the driver's own alerts",
    )
    def post(self, request):
        serializer = AcknowledgeOwnAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert = AlertService.acknowledge(request.user, serializer.validated_data['alert_id'])
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)