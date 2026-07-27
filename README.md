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
fixtures. Copy `.env.example` to `.env` for local configuration; never commit
the resulting `.env` file.
