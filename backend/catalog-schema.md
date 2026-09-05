# Catalog schema

This merchant's catalog is exposed as a plain, structured REST API — independent
of our own buyer agent. Any script, or any other AI agent, can query it
directly with `curl` or an HTTP client and get clean, structured data back.

**`price_inr` is always whole rupees, everywhere in this API — never paise.**
The only place in the entire codebase that converts to paise is immediately
before the Razorpay order-creation call, internal to this merchant's own
payment flow; nothing paise-denominated ever appears in this API.

## `GET /api/catalog`

Query params (all optional):

| Param | Type | Description |
|---|---|---|
| `category` | string | Exact match, e.g. `Electronics`, `Apparel`, `Home & Kitchen`, `Books & Stationery` |
| `max_price` | integer | Upper bound on `price_inr` (whole rupees) |
| `tags` | string | Comma-separated; matches if the product has ANY of the given tags |

Response: a JSON array of product objects.

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable product identifier |
| `name` | string | Display name |
| `description` | string \| null | Short description |
| `price_inr` | integer | Price in **whole rupees** |
| `category` | string | One of the categories above |
| `stock` | integer | Units currently available; `0` means out of stock |
| `policy_returns` | string \| null | e.g. `"7-day return"` |
| `policy_shipping` | string \| null | e.g. `"2-day shipping"` |
| `tags` | string[] | Free-form tags for matching (e.g. `["audio", "wireless"]`) |

Example:

```bash
curl "http://localhost:8000/api/catalog?category=Electronics&max_price=2000"
```

```json
[
  {
    "id": "ele-001",
    "name": "Wireless Earbuds",
    "description": "Bluetooth 5.3 earbuds, 24h battery with case",
    "price_inr": 1799,
    "category": "Electronics",
    "stock": 25,
    "policy_returns": "7-day return",
    "policy_shipping": "2-day shipping",
    "tags": ["audio", "wireless", "gadget"]
  }
]
```

## `GET /api/catalog/{product_id}/quote`

Returns a signed, time-boxed quote — price and availability locked for the
next 10 minutes. Mirrors how AP2/ACP-style agent commerce protocols structure
a "quote" object as a distinct step between browsing and buying.

```bash
curl "http://localhost:8000/api/catalog/ele-001/quote"
```

```json
{
  "product_id": "ele-001",
  "price_inr": 1799,
  "available": true,
  "quote_expires_at": "2026-09-05T10:15:00.000000+00:00"
}
```

## Alternative: the same catalog over MCP

The same two operations (`search_catalog`, `get_quote`) are also exposed as a
Model Context Protocol server (`backend/mcp_server/`), so any MCP-compatible
agent — not only one that speaks plain REST — can browse and quote this
merchant's catalog the same way. See `backend/mcp_server/README.md` for how to
connect a client to it.
