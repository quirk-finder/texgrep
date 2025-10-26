from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from indexer.build_index import build_index

from search.service import get_search_service


class Command(BaseCommand):
    help = "Ingest and index LaTeX sources into OpenSearch"

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--source",
            default="samples",
            choices=["samples", "arxiv"],
            help="Corpus to ingest",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Maximum number of files to ingest"
        )

    def handle(self, *args, **options):  # type: ignore[override]
        source = options["source"]
        limit = options.get("limit")
        service = get_search_service()
        try:
            documents = build_index(service, source=source, limit=limit)
        except (
            NotImplementedError
        ) as exc:  # pragma: no cover - depends on external tooling
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(f"Indexed {len(documents)} documents from {source}")
        )
