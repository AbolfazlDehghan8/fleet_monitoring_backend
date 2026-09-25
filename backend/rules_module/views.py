from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdmin

from .serializers import RuleListQuerySerializer, RuleSerializer, RuleWriteSerializer
from .services import RuleService


class RuleListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        parameters=[OpenApiParameter('is_active', bool, description='Filter by active flag')],
        responses={200: RuleSerializer(many=True), 400: 'Invalid is_active'},
        summary='List rules',
        description='Optional ?is_active=true/false filter',
    )
    def get(self, request):
        query = RuleListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rules = RuleService.list_rules(is_active=query.validated_data.get('is_active'))
        return Response(RuleSerializer(rules, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=RuleWriteSerializer,
        responses={201: RuleSerializer, 400: 'Bad Request'},
        summary='Create a rule',
        description='Takes effect for new telemetry immediately (the rule cache is invalidated).',
    )
    def post(self, request):
        serializer = RuleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = RuleService.create_rule(request.user, serializer.validated_data)
        return Response(RuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class RuleDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(responses={200: RuleSerializer, 404: 'Not Found'}, summary='Retrieve a rule')
    def get(self, request, rule_id):
        return Response(RuleSerializer(RuleService.get_rule(rule_id)).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=RuleWriteSerializer,
        responses={200: RuleSerializer, 400: 'Bad Request', 404: 'Not Found'},
        summary='Update a rule',
    )
    def patch(self, request, rule_id):
        rule = RuleService.get_rule(rule_id)
        serializer = RuleWriteSerializer(instance=rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        rule = RuleService.update_rule(request.user, rule, serializer.validated_data)
        return Response(RuleSerializer(rule).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 404: 'Not Found'}, summary='Delete a rule')
    def delete(self, request, rule_id):
        RuleService.delete_rule(request.user, rule_id)
        return Response(status=status.HTTP_204_NO_CONTENT)