"""Stretch: MCP-based catalog (plan section 9b). Re-exposes the same catalog
data as the REST /api/catalog endpoints, but over MCP, so any MCP-compatible
agent (not just our own buyer agent) can browse this merchant's catalog.

Runs in its own isolated venv deliberately — installing the mcp SDK into the
main backend's venv upgraded starlette to a version incompatible with our
pinned FastAPI and broke the whole app. Keeping this fully separate means it
can never do that again. It reads the same SQLite file the main backend
writes, read-only, via plain sqlite3 (no dependency on the main app's code).

All prices are WHOLE RUPEES, same convention as the rest of the project
(plan section 0) — this server does no payment operations, so there is no
paise conversion here at all.

Run with: venv/Scripts/python.exe server.py
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from mcp.server.mcpserver import MCPServer

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "agentic_commerce.db")

mcp = MCPServer(name="agentic-commerce-catalog", version="1.0.0")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@mcp.tool(description="Search the merchant catalog by category, max price (whole rupees), or tags.")
def search_catalog(category: str | None = None, max_price_inr: int | None = None, tags: list[str] | None = None) -> dict:
    con = _connect()
    try:
        query = "SELECT * FROM products WHERE 1=1"
        params: list = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if max_price_inr is not None:
            query += " AND price_inr <= ?"
            params.append(max_price_inr)
        rows = con.execute(query, params).fetchall()

        products = []
        for r in rows:
            row_tags = json.loads(r["tags"]) if r["tags"] else []
            if tags and not (set(t.lower() for t in tags) & set(t.lower() for t in row_tags)):
                continue
            products.append({
                "id": r["id"], "name": r["name"], "price_inr": r["price_inr"],
                "category": r["category"], "stock": r["stock"], "tags": row_tags,
                "policy_returns": r["policy_returns"], "policy_shipping": r["policy_shipping"],
            })
        return {"products": products}
    finally:
        con.close()


@mcp.tool(description="Get a signed, time-boxed quote (price + availability) for one product by id.")
def get_quote(product_id: str) -> dict:
    con = _connect()
    try:
        row = con.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return {"error": "product not found"}
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        return {
            "product_id": row["id"],
            "price_inr": row["price_inr"],
            "available": row["stock"] > 0,
            "quote_expires_at": expires.isoformat(),
            "quote_id": str(uuid.uuid4()),
        }
    finally:
        con.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
