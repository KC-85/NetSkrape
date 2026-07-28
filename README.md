# NetSkrape

A production-oriented web scraping project, currently under development.

## Project layout

```text
src/netskrape/
├── auth/          # Authenticated sessions and credentials workflows
├── crawling/      # HTTP clients, scheduling, retries, and crawl policies
├── extraction/    # Parsing, validation, and domain models
├── storage/       # Persistence interfaces and implementations
├── cli.py         # Command-line entry point
├── config.py      # Application configuration
├── exceptions.py  # Package-specific exception hierarchy
└── scraper.py     # High-level scraping orchestration
```

Tests are separated into fast unit tests, integration tests, and reusable
fixtures. Use `.env.example` as a reference for environment variables. Export
those values in your shell or process environment; never commit local secrets.

## Command line

Run a crawl and append normalized pages to a JSON Lines file:

```bash
netskrape crawl https://example.com \
  --output netskrape-results.jsonl \
  --max-pages 100 \
  --max-depth 3 \
  --workers 5
```

To retain historical snapshots in SQLite instead:

```bash
netskrape crawl https://example.com \
  --database netskrape.db \
  --max-pages 100 \
  --max-depth 3 \
  --workers 5
```

Discovered links are restricted to the seed domains by default. The command
returns exit code `0` for complete success, `1` for a runtime failure, `2` for
invalid usage, and `3` when the crawl completes with one or more page failures.
