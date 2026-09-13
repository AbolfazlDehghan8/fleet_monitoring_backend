from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdmin

from .models import Rule
from .serializers import RuleSerializer, RuleWriteSerializer
from .services import RuleService
from fleet_monitoring.error_utils import validation_error_response


class RuleListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        responses={200: RuleSerializer(many=True)},
        summary='List rules',
        description='Optional ?is_active=true/false filter',
    )
    def get(self, request):
        is_active_param = request.query_params.get('is_active')
        is_active = None
        if is_active_param is not None:
            is_active = is_active_param.lower() == 'true'
        rules = RuleService.list_rules(is_active=is_active)
        return Response(RuleSerializer(rules, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=RuleWriteSerializer,
        responses={201: RuleSerializer, 400: 'Bad Request'},
        summary='Create a rule',
    )
    def post(self, request):
        serializer = RuleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rule = RuleService.create_rule(request.user, serializer.validated_data)
        except ValidationError as exc:
            return validation_error_response(exc)

        return Response(RuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class RuleDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(responses={200: RuleSerializer, 404: 'Not Found'}, summary='Retrieve a rule')
    def get(self, request, rule_id):
        try:
            rule = RuleService.get_rule(rule_id)
        except Rule.DoesNotExist:
            return Response({'detail': 'Rule not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RuleSerializer(rule).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=RuleWriteSerializer,
        responses={200: RuleSerializer, 400: 'Bad Request', 404: 'Not Found'},
        summary='Update a rule',
    )
    def patch(self, request, rule_id):
        try:
            rule = RuleService.get_rule(rule_id)
        except Rule.DoesNotExist:
            return Response({'detail': 'Rule not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RuleWriteSerializer(instance=rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            rule = RuleService.update_rule(request.user, rule, serializer.validated_data)
        except ValidationError as exc:
            return validation_error_response(exc)

        return Response(RuleSerializer(rule).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 404: 'Not Found'}, summary='Delete a rule')
    def delete(self, request, rule_id):
        try:
            RuleService.delete_rule(request.user, rule_id)
        except ValidationError:
            return Response({'detail': 'Rule not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)