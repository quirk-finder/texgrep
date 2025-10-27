from __future__ import annotations

import time
import uuid

import structlog
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .providers import get_provider, get_provider_name
from .serializers import SearchRequestSerializer, SearchResponseSerializer
from .tasks import reindex_task

logger = structlog.get_logger(__name__)

INVALID_REQUEST_CODE = "invalid_request"
INTERNAL_ERROR_CODE = "internal_error"


@api_view(["GET"])
def health_view(request):  # type: ignore[override]
    return Response({"status": "ok"})


@api_view(["POST"])
@ratelimit(key="ip", rate="60/m", block=True)
@ratelimit(key="ip", rate="1000/d", block=True)
def search_view(request):  # type: ignore[override]
    start_time = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    provider_name = get_provider_name()
    mode = request.data.get("mode") or "literal"

    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        took_ms = int((time.perf_counter() - start_time) * 1000)
        logger.bind(
            request_id=request_id,
            provider=provider_name,
            mode=mode,
        ).info(
            "search.invalid_request",
            took_ms=took_ms,
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=serializer.errors,
        )
        return Response(
            {
                "message": "Invalid search request",
                "code": INVALID_REQUEST_CODE,
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    search_request = serializer.validated_data["parsed"]
    mode = search_request.mode
    log = logger.bind(request_id=request_id, provider=provider_name, mode=mode)

    if search_request.mode == "regex" and provider_name != "zoekt":
        took_ms = int((time.perf_counter() - start_time) * 1000)
        log.info(
            "search.invalid_request",
            took_ms=took_ms,
            status_code=status.HTTP_400_BAD_REQUEST,
            reason="regex_not_supported",
        )
        return Response(
            {
                "message": "regex is only supported with Zoekt",
                "code": INVALID_REQUEST_CODE,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    provider = get_provider(provider_name)
    try:
        response = provider(search_request)
    except Exception:
        took_ms = int((time.perf_counter() - start_time) * 1000)
        log.error(
            "search.internal_error",
            took_ms=took_ms,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            exc_info=True,
        )
        return Response(
            {
                "message": "Internal server error",
                "code": INTERNAL_ERROR_CODE,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    took_end_to_end_ms = int((time.perf_counter() - start_time) * 1000)
    payload = SearchResponseSerializer.from_response(
        response,
        took_end_to_end_ms=took_end_to_end_ms,
    )
    log.info(
        "search.success",
        took_ms=took_end_to_end_ms,
        status_code=status.HTTP_200_OK,
        hits=len(response.hits),
        total=response.total,
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
