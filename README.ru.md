# printables-mcp

[English](README.md) · **Русский**

[![PyPI - Version](https://img.shields.io/pypi/v/printables-mcp)](https://pypi.org/project/printables-mcp/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/printables-mcp)
![PyPI - Status](https://img.shields.io/pypi/status/printables-mcp)
[![CI](https://github.com/feodor-ra/printables-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/feodor-ra/printables-mcp/actions/workflows/ci.yml)

[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.feodor--ra%2Fprintables--mcp-blue)](https://registry.modelcontextprotocol.io/?q=printables-mcp)
[![feodor-ra/printables-mcp MCP server](https://glama.ai/mcp/servers/feodor-ra/printables-mcp/badges/score.svg)](https://glama.ai/mcp/servers/feodor-ra/printables-mcp)

**[MCP](https://modelcontextprotocol.io)-сервер для [Printables.com](https://www.printables.com).** Через него ИИ-агент ищет 3D-модели, читает их карточки, смотрит список файлов и получает прямые ссылки на скачивание.

Сервер обращается напрямую к публичному GraphQL API Printables: без парсинга HTML, без браузера и без аккаунта. Все инструменты только читают данные и возвращают структурированный результат (JSON со схемой вывода), поэтому агент получает точные поля, а не текст.

## Установка

```bash
uv tool install printables-mcp
```

Затем подключите команду `printables-mcp` в MCP-клиенте. Claude Code:

```bash
claude mcp add printables -s user -- printables-mcp
```

Любой другой клиент с транспортом stdio:

```json
{
  "mcpServers": {
    "printables": { "command": "printables-mcp" }
  }
}
```

Без установки: `uvx printables-mcp`.

## Инструменты

| Инструмент | Что делает |
|---|---|
| `search_models` | Поиск по тексту с пагинацией (`limit`, `offset`, общее число результатов) и фильтрами: категория, цена (`free` / `paid`), лицензии, опубликовано за N дней, есть фото печати. Сортировки: по релевантности, популярности, новизне, рейтингу, числу печатей. |
| `get_model` | Полная карточка модели: описание в Markdown, теги, путь категории, лицензия, материалы, принтер, время печати, вес филамента, фото, PDF, источники ремикса, статистика, цена. |
| `list_model_files` | Все группы файлов одним запросом: файлы модели (STL/3MF/STEP…), G-code с принтером, материалом, высотой слоя, соплом и временем печати, файлы SLA, прочие файлы, ZIP-архивы. |
| `get_download_links` | Прямые ссылки на скачивание (живут 24 часа) для всех или выбранных файлов, запрашиваются параллельно. Для файлов платных моделей и моделей Printables Club по каждому файлу приходит причина отказа, остальные ссылки при этом выдаются. |
| `list_categories` | Все категории с полным путём (ID для фильтра поиска). |
| `list_licenses` | Все лицензии (ID для фильтра поиска). |
| `get_author` | Профиль автора по ID, нику или ссылке на профиль. |
| `list_author_models` | Модели автора постранично (курсор), сортировка: новые, старые, по лайкам, скачиваниям, рейтингу или числу печатей. |

Модели и авторов можно передавать по ID или ссылкой на printables.com (префиксы локали вроде `/de/` поддерживаются).

## Ограничения

- Доступ только анонимный: платные модели и модели Printables Club видны, но их файлы скачать нельзя.
- API не документирован и может поменяться без предупреждения. Сквозные тесты (`just test-live`) проверяют его на живом сервисе.

## Разработка

```bash
uv sync
just lint       # ruff format/check + ty
just test       # pytest со 100% покрытием веток
just test-live  # сквозные тесты против реального API
```

## Лицензия

[MIT](LICENSE)
