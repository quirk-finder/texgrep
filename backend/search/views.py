from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import SearchRequestSerializer, SearchResponseSerializer
from .service import get_search_service
from .tasks import reindex_task


@api_view(["GET"])
def health_view(request):  # type: ignore[override]
    return Response({"status": "ok"})


@api_view(["POST"])
def search_view(request):  # type: ignore[override]
    serializer = SearchRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    search_request = serializer.validated_data["parsed"]
    service = get_search_service()
    response = service.search(search_request)
    payload = SearchResponseSerializer.from_response(response)
    return Response(payload)


@api_view(["POST"])
def reindex_view(request):  # type: ignore[override]
    source = request.data.get("source", "samples")
    if source not in {"samples", "arxiv"}:
        return Response({"detail": "Unknown source"}, status=status.HTTP_400_BAD_REQUEST)
    limit_value = request.data.get("limit")
    limit = int(limit_value) if limit_value is not None else None
    task = reindex_task.delay(source=source, limit=limit)
    return Response({"task_id": task.id, "status": "queued"}, status=status.HTTP_202_ACCEPTED)
