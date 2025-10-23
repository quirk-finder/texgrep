from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch

from search.backends import get_index_definition


class Command(BaseCommand):
    help = "Create the OpenSearch index with the texgrep mapping"

    def handle(self, *args, **options):  # type: ignore[override]
        client = OpenSearch(hosts=[settings.OPENSEARCH_HOST], verify_certs=False)
        index_name = settings.OPENSEARCH_INDEX
        definition = get_index_definition()
        if client.indices.exists(index=index_name):
            self.stdout.write(self.style.WARNING(f"Index '{index_name}' already exists"))
            return
        client.indices.create(index=index_name, body=definition)
        self.stdout.write(self.style.SUCCESS(f"Created index '{index_name}'"))
