# Track 01 — AI Growth & Agentic Commerce
## Implementation Plan

**Goal:** Build a merchant that's fully transactable by an AI buyer agent, end to end, on Razorpay test-mode APIs — with visible guardrails, an audit trail, and graceful failure handling.

**Important note on the LLM model name:** Google's Gemini model lineup changes
often — models get deprecated and replaced on a rolling basis. Don't hardcode a
model name anywhere in the code. Before writing any Gemini-related code, check
**Google AI Studio → your project → Dashboard** for whichever model is currently
listed under your **free tier**, and put that exact model ID in `GEMINI_MODEL` in
`.env`. Treat the model name purely as a config value.

---

## 0. Unit convention (read this first)

- Every `*_inr` field (`price_inr`, `amount_inr`, `max_txn_inr`, `confirm_above_inr`, `max_daily_spend_inr`) stores **whole rupees as an integer**, everywhere: DB, guardrail config, agent tool inputs/outputs, and the audit log.
- Razorpay's API requires **paise**. The conversion (`rupees * 100`) happens **only** inside `create_razorpay_order()` in section 6, immediately before the Razorpay client call.
- Before considering any phase done, grep the codebase for `* 100` and `/ 100` — there should be exactly one match, in that one function. If there's a second one anywhere, that's a bug.

---

## 1. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11 + FastAPI | fast to wire LLM tool-calling, async webhook handling |
| Agent LLM | Google Gemini (free tier), via `google-genai` SDK, function calling | free, sufficient for a 3-tool chain |
| Payments | Razorpay test-mode: Orders API, Payment Links API, Webhooks | required by the track |
| DB | SQLite (Postgres if team is comfortable) | catalog, orders, audit log, guardrail config |
| Frontend | Next.js + Tailwind | buyer-agent chat view + merchant audit dashboard |
| Queue/async | FastAPI BackgroundTasks | webhook processing |

Setup commands:
```bash
# backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn razorpay google-genai sqlalchemy pydantic python-dotenv tenacity

# frontend
npx create-next-app@latest merchant-dashboard --typescript --tailwind --app
```

`tenacity` is used for retry/backoff on Gemini free-tier rate limits — see section 4.

**Razorpay test-mode setup:**
1. Sign up at razorpay.com → switch to **Test Mode**
2. Settings → API Keys → generate test Key ID + Key Secret
3. Settings → Webhooks → add endpoint (use ngrok/localtunnel during dev) → subscribe to `payment.captured`, `payment.failed`, `order.paid`
4. Use Razorpay's documented test card numbers to simulate both success and decline

**Gemini setup:**
1. Go to **aistudio.google.com** → your project (or create one)
2. **API Keys** in the left sidebar → copy the key
3. Check the **Dashboard/model picker** for which model is currently under the **free tier** for your project — put that model ID in `.env` as `GEMINI_MODEL`
4. Note your **rate limits** (Rate Limit tab in AI Studio) — free tier is request-per-minute limited, which matters for section 4

---

## 2. Data model

```sql
-- Catalog: the agent-readable product surface
-- price_inr is WHOLE RUPEES, not paise (see section 0)
CREATE TABLE products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  price_inr INTEGER NOT NULL,       -- rupees
  category TEXT NOT NULL,
  stock INTEGER NOT NULL,
  policy_returns TEXT,              -- e.g. "7-day return"
  policy_shipping TEXT,
  tags TEXT                         -- JSON array, for agent matching
);

-- Guardrail config: bounds the agent operates within (all values in rupees)
CREATE TABLE guardrails (
  id INTEGER PRIMARY KEY,
  max_txn_inr INTEGER NOT NULL,          -- hard cap, single transaction
  confirm_above_inr INTEGER NOT NULL,    -- soft cap, needs human confirm
  blocked_categories TEXT,               -- JSON array
  max_daily_spend_inr INTEGER NOT NULL
);

-- Orders: transaction lifecycle
CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  razorpay_order_id TEXT,
  razorpay_payment_id TEXT,
  product_id TEXT REFERENCES products(id),
  amount_inr INTEGER NOT NULL,      -- rupees; converted to paise only when calling Razorpay
  status TEXT NOT NULL,   -- created, confirmed_pending, paid, failed, recovered
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log: every decision + action, timestamped
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  event_type TEXT NOT NULL,   -- catalog_query, candidate_selected, guardrail_check,
                               -- guardrail_blocked, confirmation_requested,
                               -- payment_initiated, payment_result, failure_handled,
                               -- llm_unavailable
  detail JSON NOT NULL,       -- structured explanation, not free text; amounts in rupees
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Seed 15-20 products across 3-4 categories so the agent has real choices to reason over — don't seed just 3 products, it makes the "decision" look fake.

---

## 3. Agent-readable catalog (the merchant side)

Expose a clean, structured endpoint any agent (yours or a judge's own script) could call — this is what makes the merchant "AI-buyer ready," independent of your specific buyer agent. All prices returned here are in rupees.

```python
# GET /api/catalog?category=&max_price=&tags=
@app.get("/api/catalog")
def get_catalog(category: str = None, max_price: int = None, tags: str = None):
    # returns structured product list: id, name, price_inr (rupees), stock, policies
    ...

# GET /api/catalog/{product_id}/quote
# returns a signed, time-boxed quote: price + availability lock for N minutes
# this mirrors how AP2/ACP structure a "quote" object — mention this in your pitch
@app.get("/api/catalog/{product_id}/quote")
def get_quote(product_id: str):
    ...
```

Publish a short `catalog-schema.md` describing the fields, and state explicitly that `price_inr` is whole rupees. This single artifact does a lot of work in judging: it shows you're solving "make the merchant transactable by *any* AI buyer," not just demoing your own bot talking to itself.

---

## 4. Buyer agent — Gemini + function calling

### 4.1 Define tools (Gemini function declarations)

```python
from google import genai
from google.genai import types

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
```

### 4.2 Agent loop, with retry for free-tier rate limits

Free-tier Gemini has fairly tight requests-per-minute limits. Wrap calls with
`tenacity` so a transient 429 doesn't kill your live demo.

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=20))
def call_gemini(contents, model_name):
    return client.models.generate_content(
        model=model_name,       # from GEMINI_MODEL env var — do not hardcode
        contents=contents,
        config=types.GenerateContentConfig(tools=[tools]),
    )

def run_agent_turn(user_message: str, session_id: str, model_name: str):
    contents = build_contents(history, user_message)  # your conversation history builder
    response = call_gemini(contents, model_name)

    candidate = response.candidates[0]
    for part in candidate.content.parts:
        if part.function_call:
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)

            log_audit(session_id, fn_name, fn_args)          # log BEFORE executing
            result = execute_tool(fn_name, fn_args)
            log_audit(session_id, f"{fn_name}_result", result)  # log AFTER executing

            # feed the function result back to Gemini as a function_response part,
            # then call call_gemini() again to continue the loop until a final
            # text response (no more function_call parts) comes back
            contents = append_function_response(contents, fn_name, result)
            response = call_gemini(contents, model_name)
            candidate = response.candidates[0]

    return response
```

**Log every function call before and after execution** — that's what makes your audit trail real instead of a post-hoc summary you wrote yourself.

### 4.3 Known risk to test early

Test the exact 3-tool chain (search → guardrail check → create order) early,
in isolation, before building anything on top of it. Multi-step function-calling
reliability can be inconsistent, and this chain is the core of your demo — you
want to discover any flakiness on hour 10, not hour 40.

---

## 5. Guardrail layer (this is your differentiator — build it first, not last)

All comparisons here are rupees-to-rupees — no unit conversion happens in this function.

```python
def check_guardrails(product_id: str, amount_inr: int, session_id: str) -> dict:
    g = get_guardrail_config()
    product = get_product(product_id)

    if product.category in g.blocked_categories:
        result = {"allowed": False, "reason": f"category '{product.category}' is blocked"}
    elif amount_inr > g.max_txn_inr:
        result = {"allowed": False, "reason": f"₹{amount_inr} exceeds hard cap ₹{g.max_txn_inr}"}
    elif amount_inr > g.confirm_above_inr:
        result = {"allowed": "needs_confirmation", "reason": f"₹{amount_inr} exceeds ₹{g.confirm_above_inr}, human confirmation required"}
    elif get_daily_spend(session_id) + amount_inr > g.max_daily_spend_inr:
        result = {"allowed": False, "reason": "would exceed daily spend cap"}
    else:
        result = {"allowed": True, "reason": "within all bounds"}

    log_audit(session_id, "guardrail_check", {**result, "amount_inr": amount_inr, "product_id": product_id})
    return result
```

Demo moment: seed the guardrail config with a visible cap (e.g. ₹2000 hard cap, ₹1000 confirmation threshold), then in your live demo ask for something at ₹1500 — show it pause and ask the human to confirm — and something at ₹3000 — show it refuse outright.

---

## 6. Razorpay integration — the one place the paise conversion happens

```python
import razorpay
client_rzp = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount_inr: int, product_id: str, session_id: str):
    # THE ONLY unit conversion in the whole codebase: rupees -> paise, right here.
    amount_paise = amount_inr * 100
    order = client_rzp.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "notes": {"product_id": product_id, "session_id": session_id}
    })
    log_audit(session_id, "payment_initiated", {"razorpay_order_id": order["id"], "amount_inr": amount_inr})
    save_order(order["id"], product_id, amount_inr, status="created")  # stored in rupees
    return order

# Webhook handler — this is what confirms/fails the loop
@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    payload = await request.json()
    verify_webhook_signature(request)  # always verify, even in test-mode

    event = payload["event"]
    order_id = payload["payload"]["payment"]["entity"]["order_id"]

    if event == "payment.captured":
        update_order_status(order_id, "paid")
        log_audit_by_order(order_id, "payment_result", {"status": "captured"})
        notify_merchant_fulfillment(order_id)
    elif event == "payment.failed":
        update_order_status(order_id, "failed")
        log_audit_by_order(order_id, "payment_result", {"status": "failed"})
        handle_payment_failure(order_id)  # see section 7

    return {"status": "ok"}
```

---

## 7. Failure handling (don't skip this — it's explicitly in "the bar")

```python
def handle_payment_failure(order_id: str):
    order = get_order(order_id)   # order.amount_inr is rupees
    product = get_product(order.product_id)

    if product.stock <= 0:
        alt = find_alternative(product.category, product.price_inr, tolerance=0.15)
        log_audit_by_order(order_id, "failure_handled", {
            "cause": "out_of_stock",
            "action": "suggested_alternative" if alt else "no_alternative_available",
            "alternative_id": alt.id if alt else None
        })
        return {"message": "That item is out of stock — here's a similar option within your budget." if alt
                else "That item is out of stock and no close alternative was found."}
    else:
        log_audit_by_order(order_id, "failure_handled", {"cause": "payment_declined", "action": "retry_prompt"})
        return {"message": "Payment didn't go through — want to try a different card or method?"}
```

For your live demo: use Razorpay's documented test card numbers that trigger a decline deliberately, so this path fires reliably on stage instead of hoping for a random failure.

**Add a second failure path specifically for the LLM:** if `call_gemini()`
exhausts its retries (persistent rate limit or API error), log it as its own
audit event type (`llm_unavailable`) and surface a clean message ("the
assistant is briefly unavailable, please retry in a moment") instead of a raw
stack trace. This is a real failure mode with a free-tier API — worth its own
explicit handling, and a legitimate second "graceful failure" moment to point to.

---

## 8. Audit trail (build this early — it's your highest-leverage feature)

Backend: a single endpoint that reconstructs the full timeline for a session. All amounts shown are rupees, matching what a human reading the dashboard expects.

```python
@app.get("/api/audit/{session_id}")
def get_audit_trail(session_id: str):
    events = query_audit_log(session_id)  # ordered by created_at
    return {"session_id": session_id, "events": events}
```

Frontend: render as a vertical timeline — event type, human-readable detail, timestamp. Don't just dump JSON; label each event type with a short plain-language description ("Checked ₹1500 purchase against guardrails → required confirmation").

---

## 9. Stretch: upsell/cross-sell agent

Only after sections 1-8 are solid. A second, smaller Gemini call (same function-calling pattern as section 4, just one tool) that reasons over the cart + selected product's `tags` to suggest one complementary item, logged the same way through `audit_log`. Keep it to one clean interaction — a shallow but working stretch feature beats a half-built one.

### 9b. Optional stretch: MCP-based catalog

If sections 1-8 and any planned stretch work are done with meaningful time left,
consider re-exposing section 3's catalog as an **MCP server** (via the official
Python MCP SDK) instead of, or alongside, the plain REST endpoint, with your
buyer agent as an MCP client. This upgrades the pitch from "our bot talks to our
store" to "any MCP-compatible agent can transact with this merchant." Check
`google-genai`'s current MCP integration docs when you get here, since this is a
newer part of the SDK and worth a quick doc check rather than assuming a method
name. Only attempt this once the core flow (sections 1-8) is fully working and
demoed successfully at least once.

---

## 10. 48-hour timeline

| Hours | Task |
|---|---|
| 0–4 | Razorpay test-mode account, catalog schema + seed data (15-20 products), basic order→payment flow with NO AI — get money moving first |
| 4–8 | Webhook handling + order status lifecycle working reliably |
| 8–12 | **Gemini smoke test**: confirm your exact model ID works, confirm the 3-tool function-calling chain works in isolation, before building anything on top |
| 12–18 | Buyer agent: full conversational flow with `search_catalog` |
| 18–22 | `check_guardrails` tool + guardrail config + confirmation flow |
| 22–26 | `create_order` tool wired to Razorpay, full happy path working end-to-end |
| 26–33 | Audit trail: backend endpoint + frontend timeline UI |
| 33–39 | Failure handling: out-of-stock, payment decline, and LLM-unavailable paths, tested live |
| 39–43 | Upsell/cross-sell agent (stretch), or MCP catalog (section 9b), or docs polish |
| 43–46 | UI polish, seed clean demo data, remove debug noise |
| 46–48 | Rehearse demo script twice, fix whatever breaks |

---

## 11. Demo script (5-6 minutes)

1. **(30s)** Show the agent-readable catalog schema/doc — "any AI buyer could transact with this merchant, not just ours"
2. **(90s)** Live conversational purchase, within guardrails — fast, successful, show the audit trail updating live
3. **(60s)** Ask for something between the confirm threshold and hard cap — show the pause-and-confirm step
4. **(45s)** Ask for something over the hard cap — show a clean refusal with reason
5. **(60s)** Trigger a payment decline with a test card — show graceful recovery, not a crash
6. **(45s)** Walk the audit trail for everything that just happened — this ties the whole pitch together
7. **(30s, if built)** Upsell agent suggestion, or a second agent connecting via MCP

**Backup insurance for demo day:** free-tier rate limits mean a live demo could
hit a rate-limit error at an unlucky moment. Pre-record a clean run-through as a
backup video the night before, so a hiccup on stage doesn't cost you the whole
demo.

---

## 12. Judging bar — self-check before submitting

- [ ] Every `*_inr` value is rupees end-to-end; the only ×100 conversion is in `create_razorpay_order()` (verified by grep)
- [ ] Every money action is logged with a plain-language reason in the audit trail
- [ ] A hard spend cap exists and is demonstrably enforced (not just configured)
- [ ] A confirmation threshold exists for a "gray zone" amount
- [ ] At least one category or rule-based block is demonstrated
- [ ] One failure case (decline or stock-out) is handled without crashing, live
- [ ] The Gemini-unavailable path is handled without crashing
- [ ] The catalog is genuinely structured/queryable by an external agent, not just scraped for your own bot
- [ ] Daily/session spend limit exists (prevents runaway agent behavior)
- [ ] `GEMINI_MODEL` is read from config, not hardcoded, and matches a currently free-tier-eligible model
