# texgrep.app

A grep.app-style search experience for LaTeX source code. The MVP ships with a Django + DRF API backed by OpenSearch, a Celery worker that orchestrates ingestion, and a React/Tailwind front-end for interactive querying.

## Repository structure

| Path | Purpose |
| --- | --- |
| `backend/` | Django project (`texgrep`) and `search` app with REST API, Celery tasks, and OpenSearch integration |
| `frontend/` | React 18 + Vite + Tailwind interface with virtualized results, keyboard shortcuts, and MathJax previews |
| `indexer/` | Scripts for fetching sample corpora, preprocessing LaTeX, and building search indexes |
| `deploy/` | Docker Compose definitions for local development |
| `scripts/` | Benchmarks and utility scripts |

## Quick start

```bash
cp .env.example .env
make up
```

Services:

- Frontend: <http://localhost:5173>
- API: <http://localhost:8000/api/health>
- OpenSearch: <http://localhost:9200>
- Zoekt webserver (optional): internal port 6070

### Search providers

The backend can talk to either OpenSearch (default) or a Zoekt sidecar. Set
`SEARCH_PROVIDER=zoekt` (and optionally `ZOEKT_URL`) in your environment to
switch providers without rebuilding containers.

| Provider | Pros | Cons |
| --- | --- | --- |
| OpenSearch | Regex support, structured filters, existing ingestion pipeline | Heavier footprint, higher latency for small literal searches |
| Zoekt | Fast literal substring search, lightweight deployment | Regex + filters not yet implemented, requires separate index build |

To run Zoekt locally, bring up the sidecar alongside the backend and frontend:

```bash
docker compose -f deploy/docker-compose.yml up -d zoekt backend frontend
```

Zoekt stores indexes under the `zoekt_data` volume and listens on `http://zoekt:6070`
inside the Compose network by default.

### Developer workflow

Common targets in the provided `Makefile`:

| Command | Description |
| --- | --- |
| `make up` | Build and start all containers (backend, worker, frontend, OpenSearch, Redis) |
| `make down` | Stop the stack |
| `make reindex` | Run `python manage.py tex_reindex --source samples --limit 100` inside the backend container |
| `make web` | Start Django development server (useful for debugging) |
| `make test` | Run backend pytest suite |
| `make bench` | Execute the local latency benchmark script against the running API |

## Backend API

The `search` app exposes three endpoints:

- `GET /api/health` — basic readiness probe.
- `POST /api/search` — search LaTeX snippets. Payload:

  ```json
  {
    "q": "\\newcommand",
    "mode": "literal",
    "filters": { "source": "samples", "year": "2024" },
    "page": 1,
    "size": 20
  }
  ```

  Response:

  ```json
  {
    "hits": [
      {
        "file_id": "samples:...",
        "path": ".../sample1.tex",
        "line": 5,
        "snippet": "…<mark>\\newcommand</mark>…",
        "url": "https://example.com/samples/sample1.tex"
      }
    ],
    "total": 12,
    "took_ms": 37
  }
  ```

- `POST /api/reindex` — enqueue a Celery task to rebuild the index. Payload example:

  ```json
  { "source": "samples", "limit": 200 }
  ```

### OpenSearch mapping

The index is named `tex` by default and is created with a custom analyzer that preserves backslashes and provides an edge-ngram subfield for LaTeX commands:

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "tex_analyzer": {
          "type": "custom",
          "tokenizer": "tex_tokenizer",
          "filter": []
        },
        "command_prefix": {
          "type": "custom",
          "tokenizer": "keyword",
          "filter": ["command_edge"]
        }
      },
      "tokenizer": {
        "tex_tokenizer": {
          "type": "pattern",
          "pattern": "\\s+"
        }
      },
      "filter": {
        "command_edge": {
          "type": "edge_ngram",
          "min_gram": 1,
          "max_gram": 20
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "file_id": { "type": "keyword" },
      "path": { "type": "keyword" },
      "url": { "type": "keyword" },
      "year": { "type": "keyword" },
      "source": { "type": "keyword" },
      "commands": {
        "type": "keyword",
        "fields": {
          "prefix": { "type": "text", "analyzer": "command_prefix" }
        }
      },
      "content": {
        "type": "text",
        "analyzer": "tex_analyzer",
        "search_analyzer": "tex_analyzer",
        "term_vector": "with_positions_offsets",
        "fields": {
          "raw": { "type": "wildcard" }
        }
      }
    }
  }
}
```

Create the index via Django:

```bash
python manage.py create_tex_index
```

## Indexer pipeline

1. `indexer/fetch_samples.py` copies 50+ `.tex` files from `indexer/sample_corpus/` into a temporary workspace.
2. `indexer/preprocess.py` strips LaTeX comments, optionally runs `latexpand`, and extracts command tokens.
3. `indexer/build_index.py` converts the preprocessed files into `IndexDocument` objects and pushes them into OpenSearch via the `SearchService`.

A synchronous management command is available:

```bash
python manage.py tex_reindex --source samples --limit 100
```

## Frontend

The React SPA includes:

- A debounced search box with literal/regex toggle and filters (source, year).
- Virtualized result list with highlighted snippets, line numbers, clipboard copy, and outbound links.
- Keyboard shortcuts: `Ctrl/Cmd+K` focuses search, `Alt+R` toggles regex mode, `j`/`k` navigate results.
- MathJax renders inline LaTeX within snippets, and highlight.js styles the code blocks.

Development commands:

```bash
cd frontend
npm install
npm run dev
```

## Testing & benchmarking

Run backend tests (requires Django/DRF dependencies):

```bash
pytest
```

Benchmark local latency (expects running API and seeded index):

```bash
python scripts/bench_local.py
```

## Limitations & next steps

- Only the curated sample corpus is ingested; arXiv ingestion is stubbed.
- Regex support relies on OpenSearch `regexp` queries combined with backend validation; catastrophic patterns are rejected.
- More advanced math-aware search (e.g., via LaTeXML/MIaS) is left for future iterations.
- Authentication, rate limiting, and analytics are not yet implemented.
