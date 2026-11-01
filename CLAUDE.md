# printables-mcp

Public PyPI package: an MCP server (stdio) for Printables.com built on the official `mcp` SDK 2.x (`MCPServer`). Console script `printables-mcp` → `printables_mcp.server:main`.

**Keep this file up to date** when the API knowledge or design decisions change.

## Layout

src-layout, `src/printables_mcp/`:

- `client.py`: `PrintablesClient`, an async `httpx2` client with one `execute(query, variables)` method. Maps every failure to `PrintablesError`; retries network errors and 5xx (3 attempts, linear backoff).
- `queries.py`: the GraphQL documents.
- `models.py`: pydantic result models (structured tool output), built from raw payloads via `from_api`.
- `refs.py`: parsing model/author references (IDs, URLs, handles) and building site/media URLs.
- `markdown.py`: description HTML → Markdown (`markdownify`), site-relative targets made absolute.
- `server.py`: module-level tool functions (`TOOLS`), `create_server(transport=None)` registering them with read-only annotations, `main()`.

Repo root also has `server.json` (MCP Registry metadata), `Dockerfile` and `glama.json` (see Distribution).

## Printables API facts (verified by hand; introspection and field suggestions are disabled)

- Endpoint `https://api.printables.com/graphql/`; the website itself sits behind Cloudflare (403 for scripts), the API does not. An honest User-Agent is accepted.
- Validation errors come back as **HTTP 400 with a JSON `errors` body**: read the body before looking at the status. Out-of-range values (e.g. `limit: 101`) give a 400 with a non-JSON body.
- `searchPrints2(query, printType: print, limit ≤ 100, offset, ordering: SearchChoicesEnum, categoryId: ID, paid: PaidEnum{all,free,paid}, licenses: [ID], publishedDateLimitDays: Int, hasMake: Boolean)` → `{totalCount, items}`; `totalCount` caps at 10000.
- `print(id)` returns `null` for a missing model. `printDuration` is hours as a decimal string, `weight` grams, `ratingAvg` a decimal string, `price` a decimal string or null, `premium` = club-only.
- `getDownloadLink(id, printId, fileType: stl|gcode|sla|other|pack, source: model_detail)` → `{ok, errors{field messages}, output{link ttl}}`; paid/club files fail with `cannot_download_premium_file_as_anonymous_user`.
- `user(id)` accepts a numeric ID or `"@handle"` (case-insensitive) and returns `null` when unknown. `userModels(userId, limit, cursor, ordering)` → `{cursor, items}`; ordering is a string (`[-]date_published`, `likes_count`, `download_count`, `rating_avg`, `makes_count`), cursor is `""` on an empty page.

## Distribution

- PyPI via Trusted Publishing: `uv-publish.yml` runs on a published GitHub release (environment `pypi`, deployments limited to `v*` tags) and checks the tag against the pyproject version.
- Official MCP Registry as `io.github.feodor-ra/printables-mcp`: the `mcp-registry` job runs after the PyPI upload, logs in with GitHub OIDC and publishes `server.json` with its versions overwritten from the tag. The registry verifies PyPI ownership by the `<!-- mcp-name: io.github.feodor-ra/printables-mcp -->` line in README.md, which must be in the description of the very version being registered. Registry versions are immutable.
- `Dockerfile` + `glama.json` exist for Glama (it builds the image and lists tools over stdio, offline); CI builds and smoke-tests the image.

## Decisions

- Own implementation, not a fork of any existing Printables MCP server.
- Links only: the server never writes files to disk.
- Per-file download failures are returned per file; only model-level failures raise `ToolError`.

## Conventions

- ruff `select = ["ALL"]` (preview), ty `all = "error"`, pytest with 100% branch coverage. Suppressions use `# ruff: ignore[rule-name]`.
- Tests use `httpx2.MockTransport` with recorded responses in `tests/fixtures/` and an in-memory `mcp.Client`; live tests are marked `live` and excluded by default (`just test-live`).
- Conventional Commits, GPG-signed, no Co-Authored-By trailer.
