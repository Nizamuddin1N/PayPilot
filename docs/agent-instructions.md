# Instructions for the build agent

You have a file called `track01_final_implementation_plan.md` in this project.
Treat it as the source of truth for architecture, data model, and code
structure. Build the project described in it, following the rules below.

## Ground rules

1. **Work in phases, in the order given in section 10 (the timeline table).**
   After each phase, stop and give me a short status update: what you built,
   what you verified works, and anything you had to assume or couldn't finish.
   Don't jump ahead to a later phase until I confirm the current one is good.
2. **Get money moving before anything AI-related.** Phase 1: Razorpay test-mode
   account wired up, catalog seeded, a basic order → payment flow working with
   no agent involved. Don't touch LLM/agent code until this works end to end
   and you've shown me a successful test-mode payment.
3. **The guardrail layer and the audit log are the most important parts of this
   project, not optional polish.** If you're ever tight on time, cut the
   upsell agent or MCP stretch (section 9/9b) before you cut anything in
   sections 5 or 8. A working demo with visible guardrails and a real audit
   trail beats a feature-complete agent with no accountability trail.
4. **Use Gemini's function-calling format exactly as shown in section 4**
   (`types.FunctionDeclaration`, `types.Tool`, `part.function_call`,
   `part.function_call.args`). If you're unsure of current `google-genai` SDK
   method names, check the SDK's installed version/docs rather than guessing —
   the Python Gemini SDK has changed names/structure across versions.
5. **Confirm the exact Gemini model ID before building anything else.** Read it
   from Google AI Studio's dashboard (whatever's listed under the free tier for
   this project) and put it in `GEMINI_MODEL` in `.env`. Do not hardcode a
   model name anywhere in the code — always read it from config. If the model
   name in the plan looks outdated when you check, tell me and use the current
   one instead.
6. **Do the Gemini smoke test in hours 8-12 (section 10) before building the
   rest of the agent on top of it.** Confirm the exact 3-tool chain
   (search_catalog → check_guardrails → create_order) works in isolation
   first. If it's flaky, tell me immediately rather than building three more
   phases on a shaky foundation.
7. **Wrap every Gemini call in the retry/backoff pattern from section 4.2**
   (`tenacity`, exponential backoff, 4 attempts) to handle free-tier rate
   limits. If retries are exhausted, log an `llm_unavailable` audit event and
   return a clean user-facing message — never let a raw error or stack trace
   reach the UI.
8. **Follow the unit convention in section 0 exactly.** Every `*_inr` value —
   in the database, in agent tool inputs/outputs, and in the audit log — is
   whole rupees. The only place in the entire codebase that multiplies by 100
   to get paise is `create_razorpay_order()` in section 6, immediately before
   the Razorpay client call. Before marking any money-related phase done, grep
   for `* 100` and `/ 100` — there should be exactly one match. If there's more
   than one, stop and show me both locations before continuing.
9. **Every tool/function call the agent makes must be logged to `audit_log`
   before and after execution**, exactly as shown in section 4 — not
   summarized after the fact.
10. **Don't invent Razorpay or Gemini credentials, webhook URLs, or API
    behavior.** If you need a key, a webhook tunnel (ngrok/localtunnel), a
    specific test card number, or need to check current free-tier rate limits,
    ask me or tell me exactly what to go set up — don't stub it out silently
    and move on.
11. **Build the failure paths for real, not as a placeholder.** Out-of-stock,
    payment-decline, and Gemini-unavailable handling (section 7) need to
    actually trigger and recover during a live run — using Razorpay's real
    test-mode decline cards for the payment path — not a hardcoded "pretend
    this failed" branch.
12. **Keep the agent-readable catalog genuinely structured and independently
    queryable** (section 3) — I need to be able to hit `/api/catalog` myself
    with curl or a script that isn't your buyer agent and get clean, usable
    data back. State clearly in the schema doc that prices are whole rupees.
13. **When a phase is done, tell me exactly how to test it myself** (a curl
    command, a UI flow, a specific test card to use) rather than just saying
    "done."
14. **If something in the plan is ambiguous or you think there's a better
    approach, flag it and ask — don't silently deviate.** I'd rather answer a
    quick question than discover a design choice at hour 40.
15. Before we call this done, help me set up the **backup demo recording**
    mentioned in section 11 — a clean recorded run-through as insurance
    against a rate-limit hiccup during the live demo.
16. At the end, make sure the project satisfies every item in section 12's
    checklist. Go through it explicitly with me before we call it done.

## Current phase

Start with phase 1 (hours 0–4 in the timeline): Razorpay test-mode setup,
catalog schema + seed data, and a working order → payment flow with no AI
involved yet. Tell me what you need from me (API keys, confirmation of the
schema, etc.) before you start. Gemini setup and the smoke test come later, in
the 8-12 hour block — don't set that up yet.
