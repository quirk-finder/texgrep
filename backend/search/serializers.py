# backend/search/serializers.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass        # ← 追加
from rest_framework import serializers

from .query import QueryValidationError, parse_payload
from .types import SearchResponse


class SearchRequestSerializer(serializers.Serializer):
    q = serializers.CharField()
    mode = serializers.ChoiceField(choices=["literal", "regex"], default="literal")
    filters = serializers.DictField(required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    size = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):  # type: ignore[override]
        try:
            attrs["parsed"] = parse_payload(attrs)
        except QueryValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class SearchHitSerializer(serializers.Serializer):
    file_id = serializers.CharField()
    path = serializers.CharField()
    line = serializers.IntegerField()
    snippet = serializers.CharField()
    url = serializers.CharField()


class SearchResponseSerializer(serializers.Serializer):
    hits = SearchHitSerializer(many=True)
    total = serializers.IntegerField()
    took_ms = serializers.IntegerField()

    @classmethod
    def from_response(cls, response: SearchResponse) -> dict:
        # dataclass（slots=True 含む）→ dict（ネストも展開）
        payload = asdict(response) if is_dataclass(response) else response
        # data として渡して検証してから返す
        serializer = cls(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.data
