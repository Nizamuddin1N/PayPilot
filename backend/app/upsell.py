"""Stretch: upsell/cross-sell agent (plan section 9). A second, smaller Gemini
call with a single tool (search_catalog), triggered only right after a
successful create_order, suggesting one complementary item. Kept as one clean,
isolated interaction — not chained into the main conversation history."""

import json

from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agent_tools import search_catalog_impl
from app.audit import log_audit
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.models import Product

client = genai.Client(api_key=GEMINI_API_KEY)

search_catalog_decl = types.FunctionDeclaration(
    name="search_catalog",
    description="Search the merchant catalog by category, price range, or tags. Prices are in whole rupees.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "category": types.Schema(type="STRING"),
            "max_price_inr": types.Schema(type="INTEGER"),
            "tags": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        },
    ),
)
upsell_tools = types.Tool(function_declarations=[search_catalog_decl])


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=20), reraise=True)
def _call_gemini(contents):
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(tools=[upsell_tools]),
    )


def suggest_upsell(db: Session, session_id: str, purchased_product_id: str) -> str | None:
    product = db.query(Product).filter(Product.id == purchased_product_id).first()
    if not product:
        return None
    tags = json.loads(product.tags) if product.tags else []

    prompt = (
        f"A customer just bought '{product.name}' (category: {product.category}, tags: {tags}). "
        "Use search_catalog to find ONE complementary item — a DIFFERENT product, not this one, and only "
        "one with stock greater than 0 — that pairs well with this purchase, then write a single short, "
        "friendly one-sentence upsell pitch for that item including its price. If nothing in stock fits "
        "well, just say there's no good suggestion right now."
    )
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

    try:
        response = _call_gemini(contents)
    except Exception as e:
        log_audit(db, session_id, "llm_unavailable", {"stage": "upsell", "error": f"{type(e).__name__}: {e}"})
        return None

    candidate = response.candidates[0]
    candidates_considered: list[str] = []

    while any(part.function_call for part in candidate.content.parts):
        contents.append(candidate.content)
        function_response_parts = []
        for part in candidate.content.parts:
            if not part.function_call:
                continue
            fn_args = dict(part.function_call.args)
            result = search_catalog_impl(
                db, session_id,
                category=fn_args.get("category"),
                max_price_inr=fn_args.get("max_price_inr"),
                tags=fn_args.get("tags"),
            )
            result["products"] = [
                p for p in result["products"] if p["id"] != purchased_product_id and p["stock"] > 0
            ]
            candidates_considered.extend(p["id"] for p in result["products"])
            function_response_parts.append(types.Part.from_function_response(name="search_catalog", response=result))
        contents.append(types.Content(role="user", parts=function_response_parts))

        try:
            response = _call_gemini(contents)
        except Exception as e:
            log_audit(db, session_id, "llm_unavailable", {"stage": "upsell_after_tool", "error": f"{type(e).__name__}: {e}"})
            return None
        candidate = response.candidates[0]

    pitch = "".join(part.text for part in candidate.content.parts if part.text).strip()
    if pitch:
        # candidates_considered lists everything search_catalog returned to the model
        # across its call(s) — we don't guess which one it picked, since that can only
        # be reliably read from the pitch text itself (kept as one tool, per plan section 9).
        log_audit(db, session_id, "upsell_suggested", {
            "base_product_id": purchased_product_id,
            "candidates_considered": candidates_considered,
            "pitch": pitch,
        })
    return pitch or None
