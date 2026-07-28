# NetSkrape

NetSkrape is an asynchronous, production-oriented web scraping toolkit written
in Python. It crawls permitted pages, extracts normalized HTML content and
links, and stores historical page snapshots in JSON Lines or SQLite.

The project is under active development. Its current focus is a safe,
well-tested foundation rather than site-specific extraction.

## Features

- Asynchronous HTTP requests with `httpx`
- Bounded crawl and request concurrency
- Per-origin request rate limiting
- Configurable retries with exponential backoff and jitter
- Support for numeric and HTTP-date `Retry-After` headers
- Robots.txt retrieval, enforcement, and per-origin caching
- Fail-closed robots behavior when rules cannot be retrieved
- Domain, scheme, page-count, and traversal-depth restrictions
- Redirect validation on every redirect target
- Relative URL resolution and link deduplication
- HTML title, visible text, and link extraction
- JSON Lines and asynchronous SQLAlchemy/SQLite persistence
- Historical snapshots when the same URL is crawled repeatedly
- Sanitized logging that redacts credentials and query-string values
- Unit and end-to-end integration test coverage

## Requirements

- Python 3.12 or newer
- Internet access when crawling live websites
- Permission to crawl the selected target

NetSkrape currently extracts static HTML. Browser-rendered pages and
authentication workflows are not implemented yet.

## Installation

Clone the repository and create a virtual environment:

```bash
git clone <repository-url>
cd NetSkrape

python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For local development and testing:

```bash
python -m pip install -e ".[dev]"
```

Confirm the CLI is available:

```bash
netskrape --help
```

Without an editable installation, commands can be run directly from the source
tree:

```bash
PYTHONPATH=src python -m netskrape --help
```

## Quick start

Begin with a single-page crawl:

```bash
netskrape crawl https://example.com \
  --output results.jsonl \
  --max-pages 1 \
  --max-depth 0 \
  --workers 1
```

For a bounded multi-page crawl:

```bash
netskrape crawl https://example.com \
  --database netskrape.db \
  --max-pages 100 \
  --max-depth 3 \
  --workers 5
```

Multiple seed URLs can be supplied:

```bash
netskrape crawl \
  https://example.com/news \
  https://example.com/about \
  https://example.com/services \
  --database netskrape.db \
  --max-pages 250 \
  --max-depth 4 \
  --workers 5
```

Discovered links are restricted to the seed domains and their subdomains.
Fragments are removed before scheduling, and a URL is scheduled at most once
per crawl.

## Command-line options

```text
netskrape crawl [OPTIONS] SEED_URLS...

--output FILE       Append pages to a JSON Lines file.
                    Default: netskrape-results.jsonl

--database FILE     Store pages in SQLite instead of JSON Lines.

--max-pages N       Maximum number of unique URLs scheduled.
                    Default: 100

--max-depth N       Maximum link traversal depth.
                    Seeds are at depth 0. Default: 3

--workers N         Number of asynchronous crawl workers.
                    Default: 5
```

If `--database` is provided, SQLite is used and `--output` is ignored.

### Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Crawl completed without page failures |
| `1` | Configuration, persistence, or unexpected runtime failure |
| `2` | Invalid command-line usage |
| `3` | Crawl completed, but one or more pages failed |

A large crawl may return exit code `3` while still persisting every page that
completed successfully.

## Configuration

Configuration is read from process environment variables. `.env` files are not
loaded automatically. Use `.env.example` as a reference and export the values
in the shell or process that launches NetSkrape.

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `NETSKRAPE_USER_AGENT` | `NetSkrape/0.1` | User agent sent with requests |
| `NETSKRAPE_REQUEST_TIMEOUT_SECONDS` | `20.0` | Per-request timeout |
| `NETSKRAPE_MAX_CONCURRENCY` | `5` | Maximum concurrent HTTP requests |
| `NETSKRAPE_REQUESTS_PER_SECOND` | `1.0` | Request rate per origin |
| `NETSKRAPE_MAX_RETRIES` | `3` | Retries after the initial request |
| `NETSKRAPE_RETRY_BACKOFF_SECONDS` | `2.0` | Initial retry backoff |
| `NETSKRAPE_RESPECT_ROBOTS_TXT` | `true` | Enforce robots.txt rules |
| `NETSKRAPE_LOG_LEVEL` | `INFO` | Application logging level |

Accepted boolean values are `true`, `false`, `1`, `0`, `yes`, `no`, `on`, and
`off`, without case sensitivity.

Example configuration for a polite crawl:

```bash
export NETSKRAPE_USER_AGENT="NetSkrape/0.1 (+you@example.com)"
export NETSKRAPE_REQUESTS_PER_SECOND="0.5"
export NETSKRAPE_REQUEST_TIMEOUT_SECONDS="30"
export NETSKRAPE_MAX_RETRIES="3"
export NETSKRAPE_RETRY_BACKOFF_SECONDS="2"
export NETSKRAPE_RESPECT_ROBOTS_TXT="true"
export NETSKRAPE_LOG_LEVEL="INFO"
```

`0.5` requests per second represents approximately one request every two
seconds per origin.

## Storage

### JSON Lines

JSON Lines is the default storage backend. Each extracted page is appended as
one compact JSON object per line:

```bash
netskrape crawl https://example.com --output results.jsonl
```

The format is append-friendly and suitable for streaming or large crawls. To
create a readable copy:

```bash
python -m json.tool --json-lines results.jsonl > results.pretty.json
```

Each page record includes:

- Final page URL
- HTTP status code
- Title and normalized visible text
- Content type
- UTC fetch timestamp
- Extracted links with text, title, and `rel` values

### SQLite

SQLite stores normalized historical snapshots:

```bash
netskrape crawl https://example.com --database netskrape.db
```

The schema contains:

- `pages` — page content, metadata, and fetch time
- `links` — ordered links associated with a page snapshot

Repeated URLs are inserted as new page snapshots rather than overwriting older
records.

The database can be inspected with DB Browser for SQLite:

```bash
sqlitebrowser netskrape.db
```

Example query:

```sql
SELECT
    pages.url AS page_url,
    pages.title AS page_title,
    links.url AS link_url,
    links.text AS link_text
FROM pages
LEFT JOIN links ON links.page_id = pages.id
ORDER BY pages.id, links.position;
```

Local database files and SQLite journal files should not be committed.

## Crawl behavior

### Retries

The following transient status codes are retryable:

```text
408, 425, 429, 500, 502, 503, 504
```

Retries use capped exponential backoff with jitter. A valid `Retry-After`
header takes precedence over the calculated delay.

### Robots.txt

Robots rules are fetched once per origin and cached for the lifetime of the
client. NetSkrape refuses a URL when the configured user agent is disallowed.
It also fails closed when robots rules are unavailable.

Do not disable robots enforcement unless you own the target or have explicit
authorization and understand the implications.

### Scope and deduplication

- Only HTTP and HTTPS URLs are accepted.
- Redirect destinations are checked before being requested.
- Discovered links remain within seed domains by default.
- URL fragments are removed for deduplication.
- Query strings are retained and therefore identify distinct URLs.
- Page and depth limits are enforced before additional work is scheduled.

Sites with faceted navigation or many query-string combinations can generate a
large crawl frontier. Always begin with conservative limits.

## Architecture

```text
CLI and environment configuration
              |
              v
       Scraper orchestrator
              |
              v
       CrawlScheduler queue
          /           \
         v             v
 ScraperClient      HtmlParser
         \             /
          v           v
          ExtractedPage
                |
                v
          PageRepository
          /            \
         v              v
      JSONL          SQLAlchemy
```

Project layout:

```text
src/netskrape/
├── auth/
│   └── session.py             # Future authenticated-session support
├── crawling/
│   ├── client.py              # HTTP lifecycle, robots and retries
│   ├── policies.py            # Pure crawl-policy decisions
│   └── scheduler.py           # Queue, traversal and workers
├── extraction/
│   ├── models.py              # Immutable normalized models
│   └── parsers.py             # HTML extraction
├── storage/
│   ├── database.py            # Async engine and session lifecycle
│   ├── jsonl.py               # JSON Lines repository
│   ├── repositories.py        # Repository protocol and memory backend
│   ├── sqlalchemy.py          # SQLAlchemy repository
│   └── tables.py              # Database mappings
├── cli.py                     # CLI and concrete component composition
├── config.py                  # Environment parsing and validation
├── exceptions.py              # Package exception hierarchy
├── logging.py                 # Logging configuration and URL redaction
└── scraper.py                 # Crawl and persistence orchestration
```

## Development

Run the complete test suite:

```bash
pytest
```

Run only unit tests:

```bash
pytest tests/unit
```

Run integration tests:

```bash
pytest -m integration
```

Run linting:

```bash
flake8 --jobs 1 src tests
```

The integration tests use controlled temporary resources and
`httpx.MockTransport`; they do not crawl arbitrary live websites.

## Current limitations

- Only static HTML and XHTML are extracted.
- JavaScript rendering is not yet connected to the crawl pipeline.
- Authentication workflows are placeholders.
- There are no database migrations yet; schema evolution will require Alembic.
- Query-string canonicalization and filtering are not implemented.
- Storage currently represents pages and links, not complete crawl-run
  metadata.
- Parsing is generic; site-specific business models and extractors must still
  be implemented.

## Responsible use

Before crawling a website:

- Confirm that you have permission.
- Review its robots.txt and terms of service.
- Use an identifiable user agent where appropriate.
- Keep request rates conservative.
- Avoid collecting personal, confidential, or unnecessary data.
- Protect stored data and comply with applicable laws and policies.

NetSkrape provides technical safeguards, but the operator remains responsible
for how it is configured and used.

## Contributing

See `CONTRIBUTING.md` for contribution guidance. Keep changes focused, include
tests for behavioral changes, and ensure the full test suite and lint checks
pass before opening a pull request.

## License

NetSkrape is licensed under the GNU General Public License v3.0. See `LICENSE`
for the complete terms.
