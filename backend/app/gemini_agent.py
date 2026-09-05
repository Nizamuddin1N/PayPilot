"""Buyer agent: Gemini + function calling (plan section 4). Tool schemas and the
call pattern (types.FunctionDeclaration, types.Tool, part.function_call,
part.function_call.args) follow section 4.1/4.2 exactly."""

from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agent_tools import check_guardrails_impl, create_order_impl, search_catalog_impl
from app.audit import log_audit
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.sessions import get_history
from app.upsell import suggest_upsell

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

check_guardrails_decl = types.FunctionDeclaration(
    name="check_guardrails",
    description="Check if a proposed purchase (amount in whole rupees) is within the merchant's configured bounds",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "product_id": types.Schema(type="STRING"),
            "amount_inr": types.Schema(type="INTEGER"),
        },
        required=["product_id", "amount_inr"],
    ),
)

create_order_decl = types.FunctionDeclaration(
    name="create_order",
    description="Create a Razorpay order for the selected product — only call after guardrail check passes",
    parameters=types.Schema(
        type="OBJECT",
        properties={"product_id": types.Schema(type="STRING")},
        required=["product_id"],
    ),
)

tools = types.Tool(function_declarations=[search_catalog_decl, check_guardrails_decl, create_order_decl])


class LLMUnavailableError(Exception):
    pass


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=20), reraise=True)
def call_gemini(contents):
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(tools=[tools]),
    )


def execute_tool(db: Session, session_id: str, fn_name: str, fn_args: dict) -> dict:
    if fn_name == "search_catalog":
        return search_catalog_impl(
            db, session_id,
            category=fn_args.get("category"),
            max_price_inr=fn_args.get("max_price_inr"),
            tags=fn_args.get("tags"),
        )
    if fn_name == "check_guardrails":
        return check_guardrails_impl(db, session_id, fn_args["product_id"], fn_args["amount_inr"])
    if fn_name == "create_order":
        return create_order_impl(db, session_id, fn_args["product_id"])
    return {"error": f"unknown tool {fn_name}"}


def run_agent_turn(db: Session, session_id: str, user_message: str) -> dict:
    """Returns {"reply": str, "order": dict | None}. `order` carries the most
    recent successful create_order result from this turn, if any — the frontend
    needs that structured data to open Razorpay Checkout; it can't be parsed back
    out of the model's prose reply."""
    contents = get_history(session_id)
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    last_order = None
    last_product_id = None

    try:
        response = call_gemini(contents)
    except Exception as e:
        log_audit(db, session_id, "llm_unavailable", {"stage": "initial_call", "error": f"{type(e).__name__}: {e}"})
        return {"reply": "The assistant is briefly unavailable, please retry in a moment.", "order": None, "upsell": None}

    candidate = response.candidates[0]

    # Loop while Gemini keeps asking for tool calls, feeding results back each time.
    while any(part.function_call for part in candidate.content.parts):
        contents.append(candidate.content)  # the model's turn, including function_call parts
        function_response_parts = []

        for part in candidate.content.parts:
            if not part.function_call:
                continue
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)

            log_audit(db, session_id, f"{fn_name}_requested", fn_args)
            result = execute_tool(db, session_id, fn_name, fn_args)
            log_audit(db, session_id, f"{fn_name}_result", result)

            if fn_name == "create_order" and "order_id" in result:
                last_order = result
                last_product_id = fn_args.get("product_id")

            function_response_parts.append(
                types.Part.from_function_response(name=fn_name, response=result)
            )

        contents.append(types.Content(role="user", parts=function_response_parts))

        try:
            response = call_gemini(contents)
        except Exception as e:
            log_audit(db, session_id, "llm_unavailable", {"stage": "after_tool_call", "error": f"{type(e).__name__}: {e}"})
            return {"reply": "The assistant is briefly unavailable, please retry in a moment.", "order": last_order, "upsell": None}

        candidate = response.candidates[0]

    contents.append(candidate.content)  # persist the assistant's final reply for the next turn
    final_text = "".join(part.text for part in candidate.content.parts if part.text)

    upsell = suggest_upsell(db, session_id, last_product_id) if last_order and last_product_id else None
    return {"reply": final_text, "order": last_order, "upsell": upsell}
