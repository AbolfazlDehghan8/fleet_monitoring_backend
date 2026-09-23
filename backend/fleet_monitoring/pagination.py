from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class OptInPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def list_response(request, queryset, serializer_class, **serializer_kwargs):
    if 'page' in request.query_params or 'page_size' in request.query_params:
        paginator = OptInPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = serializer_class(page, many=True, **serializer_kwargs).data
        return paginator.get_paginated_response(data)
    return Response(serializer_class(queryset, many=True, **serializer_kwargs).data)