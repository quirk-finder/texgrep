# backend/search/serializers.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass        # ← 追加
from rest_framework import serializers

from .query import QueryValidationError, parse_payload
from .types import SearchResponse


class SnippetBlockSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["text", "math"])
    html = serializers.CharField(required=False, allow_blank=True)
    tex = serializers.CharField(required=False, allow_blank=True)
    display = serializers.BooleanField(required=False)
    marked = serializers.BooleanField(required=False)

    def validate(self, attrs):  # type: ignore[override]
        kind = attrs.get("kind")
        if kind == "text":
            if "html" not in attrs:
                raise serializers.ValidationError("Text block must include html content")
        elif kind == "math":
            if "tex" not in attrs:
                raise serializers.ValidationError("Math block must include tex content")
        return attrs


class SearchRequestSerializer(serializers.Serializer):
    q = serializers.CharField()
    mode = serializers.ChoiceField(choices=["literal", "regex"], default="literal")
    filters = serializers.DictField(required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    size = serializers.IntegerField(min_value=1, required=False)
    cursor = serializers.CharField(required=False, allow_blank=True)

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
    snippet = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    url = serializers.CharField(allow_blank=True, required=False, default="")
    blocks = SnippetBlockSerializer(many=True, required=False)


class SearchResponseSerializer(serializers.Serializer):
    hits = SearchHitSerializer(many=True)
    total = serializers.IntegerField()
    took_provider_ms = serializers.IntegerField()
    took_end_to_end_ms = serializers.IntegerField()
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    next_cursor = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    @classmethod
    def from_response(cls, response: SearchResponse, **extra_fields) -> dict:
        # dataclass（slots=True 含む）→ dict（ネストも展開）
        payload = asdict(response) if is_dataclass(response) else response
        payload.update({k: v for k, v in extra_fields.items() if v is not None})
        # data として渡して検証してから返す
        serializer = cls(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.data
