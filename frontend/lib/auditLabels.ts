import type { AuditEvent } from "./api";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export type EventDescription = {
  title: string;
  tone: Tone;
  /** Curated events are shown by default; wrapper before/after log rows are
   * hidden unless "show all events" is toggled, to keep the timeline readable
   * without losing the raw trace (plan section 8: "don't just dump JSON"). */
  curated: boolean;
};

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function describeEvent(e: AuditEvent): EventDescription {
  const d = e.detail ?? {};

  switch (e.event_type) {
    case "catalog_query": {
      const f = d.filters ?? {};
      const parts: string[] = [];
      if (f.category) parts.push(`category: ${f.category}`);
      if (f.max_price_inr != null) parts.push(`max ₹${f.max_price_inr}`);
      if (f.tags?.length) parts.push(`tags: ${f.tags.join(", ")}`);
      const filterText = parts.length ? ` (${parts.join(", ")})` : "";
      return {
        title: `Searched catalog${filterText} → ${plural(d.result_count ?? 0, "result")}`,
        tone: "info",
        curated: true,
      };
    }

    case "guardrail_check": {
      const amt = d.amount_inr != null ? `₹${d.amount_inr}` : "";
      if (d.allowed === true) {
        return { title: `Guardrail check passed — ${amt} within all bounds`, tone: "success", curated: true };
      }
      if (d.allowed === "needs_confirmation") {
        return { title: `Confirmation required — ${d.reason ?? amt}`, tone: "warning", curated: true };
      }
      return { title: `Guardrail blocked — ${d.reason ?? "purchase rejected"}`, tone: "danger", curated: true };
    }

    case "payment_initiated":
      return {
        title: `Razorpay order created for ₹${d.amount_inr} (${d.razorpay_order_id})`,
        tone: "info",
        curated: true,
      };

    case "payment_result":
      return d.status === "captured"
        ? { title: `Payment captured — ₹${d.amount_inr} (source: ${d.source})`, tone: "success", curated: true }
        : { title: `Payment failed — ₹${d.amount_inr} (source: ${d.source})`, tone: "danger", curated: true };

    case "failure_handled":
      return { title: `Failure handled — ${d.cause}: ${d.action}`, tone: "warning", curated: true };

    case "upsell_suggested": {
      const noSuggestion = /no good suggestion/i.test(d.pitch ?? "");
      return noSuggestion
        ? { title: `Upsell considered — no good match found`, tone: "neutral", curated: true }
        : { title: `Upsell suggested — "${d.pitch}"`, tone: "info", curated: true };
    }

    case "llm_unavailable":
      return {
        title: `Gemini unavailable during "${d.stage}" — clean fallback message shown to the user`,
        tone: "danger",
        curated: true,
      };

    default:
      // *_requested / *_result wrapper rows around every tool call (rule 9's
      // before/after logging) — kept in the raw trace, hidden from the curated view.
      return { title: e.event_type, tone: "neutral", curated: false };
  }
}
