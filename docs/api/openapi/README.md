# OpenAPI Schema

## Live vs snapshot

| Source | Location | When to use |
|--------|----------|-------------|
| Live | `GET /openapi.json` on running server | Always current during development |
| Snapshot | [mindwealth-v1.json](mindwealth-v1.json) | Code review, CI, offline reference |

## Regenerate snapshot

```bash
export PYTHONPATH="$(pwd)"
python scripts/export_openapi.py
```

Commit `mindwealth-v1.json` when routes or schemas change.

## Relationship to Markdown docs

- **OpenAPI**: machine-readable schemas, required fields, enums.
- **Markdown** (`services/*/endpoints/`): business context, verdict rules, curl examples, links to domain docs.

Both should share the same `operationId` as the FastAPI route decorator.
