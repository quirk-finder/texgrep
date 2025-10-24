from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from search import opensearch_client
from search.backends import get_index_definition


class Command(BaseCommand):
    help = "Create the OpenSearch index with the texgrep mapping"

    def handle(self, *args, **options):  # type: ignore[override]
        client = opensearch_client.create_client()
        index_name = settings.OPENSEARCH_INDEX
        definition = get_index_definition()
        if client.indices.exists(index=index_name):
            self.stdout.write(self.style.WARNING(f"Index '{index_name}' already exists. Updating mapping."))
            update_index(client, index_name, definition)
            self.stdout.write(self.style.SUCCESS(f"Updated index '{index_name}'"))
            return
        client.indices.create(index=index_name, body=definition)
        self.stdout.write(self.style.SUCCESS(f"Created index '{index_name}'"))


def update_index(client, index_name: str, definition: dict) -> None:
    settings = definition.get("settings") or {}
    mappings = definition.get("mappings") or {}
    client.indices.close(index=index_name)
    try:
        if settings:
            client.indices.put_settings(index=index_name, body=settings)
        if mappings:
            client.indices.put_mapping(index=index_name, body=mappings)
    finally:
        client.indices.open(index=index_name)
        client.indices.refresh(index=index_name)
