export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AuditEvent = {
  id: number;
  event_type: string;
  detail: Record<string, any>;
  created_at: string;
};

export type SessionSummary = {
  session_id: string;
  event_count: number;
  last_event_at: string;
};

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/api/audit/sessions`, { cache: "no-store" });
  if (!res.ok) throw new Error("failed to load sessions");
  return res.json();
}

export async function fetchAuditTrail(
  sessionId: string
): Promise<{ session_id: string; events: AuditEvent[] }> {
  const res = await fetch(`${API_BASE}/api/audit/${sessionId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("failed to load audit trail");
  return res.json();
}
