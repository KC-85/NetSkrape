# Contributing to NetSkrape

Thank you for considering a contribution to NetSkrape. Contributions may
include bug fixes, tests, documentation, performance improvements, storage
backends, crawl policies, and carefully scoped new features.

NetSkrape is intended to provide a safe and maintainable web-scraping
foundation. Changes should preserve its crawl safeguards, clear architectural
boundaries, and deterministic test suite.

## Before you begin

Before starting substantial work:

1. Search existing issues and pull requests for related work.
2. Open an issue for a large feature, architectural change, new dependency, or
   database-schema change.
3. Describe the problem, intended behavior, and important trade-offs.
4. Confirm that the proposed use respects website permissions, robots rules,
   privacy, and applicable policies.

Small corrections and focused bug fixes generally do not need a design issue
first.

## Development setup

Fork or clone the repository, then create an isolated environment:

```bash
git clone <repository-url>
cd NetSkrape

python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell, activate the environment with:

```powershell
venv\Scripts\Activate.ps1
```

Confirm the environment:

```bash
python --version
netskrape --help
pytest
```

NetSkrape requires Python 3.12 or newer.

## Create a focused branch

Create a branch whose name describes the work:

```bash
git switch -c fix/redirect-policy
```

Other useful patterns include:

```text
feature/postgresql-storage
fix/robots-cache
docs/database-guide
test/retry-after
refactor/parser-interface
```

Keep unrelated changes on separate branches and pull requests.

## Project architecture

Code belongs in the layer responsible for its behavior:

```text
src/netskrape/
├── crawling/       # HTTP transport, policies, queues and traversal
├── extraction/     # Normalized models and content parsing
├── storage/        # Repository contracts and persistence backends
├── auth/           # Future authenticated-session support
├── cli.py          # CLI options and concrete dependency assembly
├── config.py       # Environment parsing and validation
├── logging.py      # Logging setup and safe value formatting
└── scraper.py      # High-level crawl and persistence orchestration
```

Important boundaries:

- `client.py` retrieves resources; it does not parse or persist them.
- `parsers.py` extracts content; it does not perform network requests.
- `scheduler.py` manages traversal; it does not implement rate limiting.
- Storage implementations satisfy `PageRepository`.
- `scraper.py` coordinates components without constructing concrete services.
- `cli.py` is the composition root where concrete components are assembled.
- Pure decisions should remain in policy or model code where they can be tested
  without network, filesystem, or database access.

Prefer protocols and dependency injection when a component needs to support
multiple implementations.

## Coding standards

Follow the existing code style:

- Use type annotations for public functions, methods, and attributes.
- Prefer immutable dataclasses for value objects.
- Use `slots=True` when it is appropriate for a dataclass.
- Use modern Python syntax such as `str | None`.
- Write concise docstrings that describe behavior, not the implementation line
  by line.
- Keep functions focused and avoid combining transport, parsing, scheduling,
  and persistence logic.
- Use domain-specific exceptions from `netskrape.exceptions` at package
  boundaries.
- Preserve the original exception as the cause with `raise ... from error`.
- Use `pathlib.Path` for filesystem paths.
- Avoid substantial blocking work inside asynchronous methods.
- Never log credentials, cookies, authorization headers, response bodies, or
  unredacted query-string values.
- Keep lines within the Flake8 limit used by the repository.

Run linting before submitting:

```bash
flake8 --jobs 1 src tests
```

## Configuration changes

When adding configuration:

1. Add a typed field to `ScraperConfig`.
2. Validate direct construction in `__post_init__()`.
3. Parse and validate the corresponding environment variable in `from_env()`.
4. Add the variable to `.env.example`.
5. Document it in `README.md`.
6. Test valid, default, boundary, and malformed values.

Do not read environment variables throughout unrelated modules. Components
should receive validated configuration or explicit constructor arguments.

## Dependency changes

`pyproject.toml` is the authoritative declaration of direct dependencies.

Before adding a package:

- Confirm that the standard library or an existing dependency cannot reasonably
  solve the problem.
- Consider maintenance status, licence compatibility, security history,
  installation size, and supported Python versions.
- Add runtime dependencies under `[project.dependencies]`.
- Add development-only tools under `[project.optional-dependencies].dev`.
- Explain significant dependency additions in the pull request.

Avoid adding transitive dependencies manually.

## Testing

Every behavioral change should include tests at the lowest useful level.

### Unit tests

Unit tests belong in `tests/unit/` and should:

- Run quickly and deterministically.
- Avoid live internet access.
- Use `httpx.MockTransport` for HTTP behavior.
- Use temporary paths supplied by pytest.
- Avoid timing-dependent assertions where an injected value can be used.
- Exercise success, failure, boundary, and validation behavior.

Run unit tests with:

```bash
pytest tests/unit
```

### Integration tests

Integration tests belong in `tests/integration/` and should be marked:

```python
@pytest.mark.integration
```

Use integration tests when exercising multiple real components together, such
as:

```text
client → parser → scheduler → scraper → repository
```

Integration tests must not crawl arbitrary live websites. Use controlled mock
transports, temporary SQLite databases, and deterministic fixtures.

Run integration tests with:

```bash
pytest -m integration
```

Run the complete suite with:

```bash
pytest
```

### Test fixtures

Store reusable HTML and response fixtures in `tests/fixtures/`.

Fixtures must not contain:

- Credentials or session tokens
- Personal or confidential information
- Large copied websites
- Copyrighted datasets that cannot be redistributed

Prefer small HTML documents that demonstrate only the behavior under test.

## Database changes

Database changes require particular care because existing users may already
have crawl history.

When changing SQLAlchemy mappings:

- Keep historical snapshot behavior explicit.
- Preserve page-to-link referential integrity.
- Test repeated URLs and ordered links.
- Test transaction rollback and storage-error translation where relevant.
- Do not silently delete or overwrite existing crawl records.
- Describe compatibility implications in the pull request.

Alembic migrations are not yet configured. Until they are, discuss schema
changes before implementation and document any requirement to recreate a local
database.

Never commit generated database files:

```text
netskrape.db
*.db-journal
*.db-shm
*.db-wal
```

Small database fixtures may be committed under `tests/fixtures/` only when a
textual fixture cannot adequately test the behavior.

## Scraping safety requirements

Changes must not silently weaken the default safeguards.

In particular:

- Robots enforcement should remain enabled by default.
- A robots retrieval failure should remain fail-closed unless an explicit,
  reviewed policy changes that behavior.
- Redirect targets must be checked before they are requested.
- Domain, scheme, depth, concurrency, and page limits must be preserved.
- Retry behavior must remain bounded.
- Rate limiting must be applied per origin.
- Sensitive URL components must be redacted from logs and error output.

Do not contribute features primarily intended to bypass access controls,
CAPTCHAs, robots rules, authentication requirements, or anti-abuse systems.

Live manual testing should use a site you own, a site that explicitly permits
scraping, or a purpose-built scraping test site. Begin with conservative limits.

## Documentation

Update documentation alongside user-visible behavior.

README changes are expected when modifying:

- Installation or dependencies
- CLI commands or exit codes
- Environment variables
- Crawl behavior and safeguards
- Storage formats or database schema
- Supported Python versions
- Known limitations

Examples should be safe to copy, use conservative crawl limits, and avoid
implying that arbitrary websites may be scraped without permission.

## Commit guidance

Write commits that are small enough to review and meaningful enough to explain
the change.

Good commit subjects are imperative and specific:

```text
Validate redirect targets before fetching
Add SQLite page repository
Document crawl rate configuration
Test Retry-After HTTP-date parsing
```

Avoid vague subjects such as:

```text
Updates
Fix stuff
Changes
WIP
```

Do not commit:

- `.env` files
- Virtual environments
- Crawl output
- SQLite databases and journal files
- Credentials or tokens
- Cache directories
- Editor-specific local state

## Pull requests

A pull request should:

1. Explain the problem being solved.
2. Summarize the chosen implementation.
3. Identify important design or compatibility trade-offs.
4. Describe how the change was tested.
5. Include documentation for user-visible behavior.
6. Link the related issue when one exists.
7. Remain focused on one coherent change.

Suggested pull-request description:

```markdown
## Problem

What problem does this solve?

## Approach

How does the implementation solve it?

## Safety and compatibility

Does this affect robots handling, crawl scope, stored data, configuration,
dependencies, or existing databases?

## Verification

- [ ] Unit tests added or updated
- [ ] Integration tests added or updated where appropriate
- [ ] `pytest` passes
- [ ] `flake8 --jobs 1 src tests` passes
- [ ] Documentation updated
```

Reviewers may request changes for correctness, maintainability, missing tests,
unsafe crawling behavior, unclear ownership boundaries, or undocumented
compatibility impact.

## Reporting bugs

A useful bug report includes:

- NetSkrape and Python versions
- Operating system
- The command used, with secrets removed
- Relevant environment-variable names and non-sensitive values
- Expected and actual behavior
- A minimal reproduction
- Sanitized logs or traceback

Do not publish credentials, cookies, authorization headers, personal data, or
sensitive target URLs.

## Security reports

Do not open a public issue for a vulnerability that could expose credentials,
private crawl data, or systems. Use the repository host's private security
reporting feature when it is available, or contact the maintainers privately.

Include a clear description, affected versions, reproduction details, and
potential impact. Do not access data or systems beyond what is necessary to
demonstrate the issue safely.

## Licence

By contributing, you agree that your contribution may be distributed under the
GNU General Public License v3.0 used by this repository.
