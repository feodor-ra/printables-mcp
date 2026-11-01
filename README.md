# printables-mcp

**English** · [Русский](README.ru.md)

[![PyPI - Version](https://img.shields.io/pypi/v/printables-mcp)](https://pypi.org/project/printables-mcp/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/printables-mcp)
![PyPI - Status](https://img.shields.io/pypi/status/printables-mcp)
[![CI](https://github.com/feodor-ra/printables-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/feodor-ra/printables-mcp/actions/workflows/ci.yml)

**An [MCP](https://modelcontextprotocol.io) server for [Printables.com](https://www.printables.com)**: lets an AI agent search 3D models, read model cards, list files and get direct download links.

It talks to the public Printables GraphQL API directly: no HTML scraping, no browser, no account. All tools are read-only and return structured results (JSON with an output schema), so agents get exact fields instead of prose.

## Installation

```bash
uv tool install printables-mcp
```

Then register the `printables-mcp` command with your MCP client. Claude Code:

```bash
claude mcp add printables -s user -- printables-mcp
```

Any other client that speaks stdio:

```json
{
  "mcpServers": {
    "printables": { "command": "printables-mcp" }
  }
}
```

Without installing: `uvx printables-mcp`.

## Tools

| Tool | What it does |
|---|---|
| `search_models` | Text search with pagination (`limit`, `offset`, total count) and filters: category, price (`free` / `paid`), licenses, published within N days, has user prints. Orderings: best match, popular, latest, rating, makes count. |
| `get_model` | Full model card: description as Markdown, tags, category path, license, materials, printer, print time, filament weight, images, PDF, remix sources, stats, price. |
| `list_model_files` | Every file group in one request: model files (STL/3MF/STEP…), G-code with printer, material, layer height, nozzle and print time, SLA files, other files, ZIP packs. |
| `get_download_links` | Direct download URLs (valid 24 h) for all or selected files, fetched in parallel. Files of paid or club-only models come back with a per-file reason instead of failing the call. |
| `list_categories` | All categories with their full paths (IDs for the search filter). |
| `list_licenses` | All licenses (IDs for the search filter). |
| `get_author` | Author profile by ID, handle or profile URL. |
| `list_author_models` | An author's models, cursor-paginated, ordered by newest, oldest, likes, downloads, rating or makes. |

Models and authors can be passed as IDs or as printables.com URLs (locale prefixes such as `/de/` are fine).

## Limitations

- Anonymous access only: paid and Printables Club models are visible, but their files cannot be downloaded.
- The API is undocumented and may change without notice; the end-to-end suite (`just test-live`) checks it against the live service.

## Development

```bash
uv sync
just lint       # ruff format/check + ty
just test       # pytest with 100% branch coverage
just test-live  # end-to-end tests against the real API
```

## License

[MIT](LICENSE)
