# MCP catalog server (stretch, plan section 9b)

Re-exposes the same catalog data as the REST `/api/catalog` endpoints, but
over the Model Context Protocol — so any MCP-compatible agent, not just our
own buyer agent, can browse and quote this merchant's catalog. Read-only,
reads the same SQLite file the main backend writes.

**Deliberately isolated in its own venv.** Installing the `mcp` SDK into the
main backend's venv upgraded `starlette` to a version incompatible with our
pinned FastAPI and broke the whole app on import. This subproject has its own
venv precisely so that can never happen again — it shares no dependencies
with `backend/`.

## Setup

```bash
cd backend/mcp_server
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # (or venv/bin/pip on macOS/Linux)
```

## Run

```bash
./venv/Scripts/python.exe server.py
```

Speaks MCP over stdio — point any MCP client at this command
(`<path-to-venv-python> server.py`), e.g. Claude Desktop's MCP config, or the
included `test_client.py`, which proves the server works using the official
SDK's own client (not our code):

```bash
./venv/Scripts/python.exe test_client.py
```

## Tools exposed

- `search_catalog(category?, max_price_inr?, tags?)` — mirrors `GET /api/catalog`
- `get_quote(product_id)` — mirrors `GET /api/catalog/{id}/quote`

All prices are whole rupees, same convention as the rest of the project —
this server performs no payment operations, so no paise conversion happens
here at all.
