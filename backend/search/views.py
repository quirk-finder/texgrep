from __future__ import annotations

import time

from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .providers import get_provider, get_provider_name
from .serializers import SearchRequestSerializer, SearchResponseSerializer
from .tasks import reindex_task


@api_view(["GET"])
def health_view(request):  # type: ignore[override]
    return Response({"status": "ok"})


@api_view(["POST"])
@ratelimit(key="ip", rate="60/m", block=True)
@ratelimit(key="ip", rate="1000/d", block=True)
def search_view(request):  # type: ignore[override]
    start_time = time.perf_counter()
    serializer = SearchRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    search_request = serializer.validated_data["parsed"]
    provider_name = get_provider_name()
    if search_request.mode == "regex" and provider_name != "zoekt":
        return Response(
            {"message": "regex is only supported with Zoekt"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    provider = get_provider(provider_name)
    response = provider(search_request)
    took_end_to_end_ms = int((time.perf_counter() - start_time) * 1000)
    payload = SearchResponseSerializer.from_response(
        response,
        took_end_to_end_ms=took_end_to_end_ms,
    )
    return Response(payload)


@api_view(["POST"])
def reindex_view(request):  # type: ignore[override]
    source = request.data.get("source", "samples")
    if source not in {"samples", "arxiv"}:
        return Response(
            {"detail": "Unknown source"}, status=status.HTTP_400_BAD_REQUEST
        )
    limit_value = request.data.get("limit")
    if limit_value is not None:
        try:
            limit = int(limit_value)
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be a non-negative integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if limit < 0:
            return Response(
                {"detail": "limit must be a non-negative integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        limit = None
    task = reindex_task.delay(source=source, limit=limit)
    return Response(
        {"task_id": task.id, "status": "queued"}, status=status.HTTP_202_ACCEPTED
    )
