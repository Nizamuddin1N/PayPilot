"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAuditTrail, fetchSessions, type AuditEvent, type SessionSummary } from "@/lib/api";
import { describeEvent, type Tone } from "@/lib/auditLabels";

const SESSIONS_POLL_MS = 5000;
const EVENTS_POLL_MS = 2000;

function toDate(iso: string): Date {
  // SQLite timestamps come back without a timezone suffix but are UTC.
  const hasTz = /Z|[+-]\d\d:\d\d$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
}

function formatTime(iso: string): string {
  return toDate(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatRelative(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - toDate(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

const toneClasses: Record<Tone, { dot: string; bg: string; border: string; text: string }> = {
  neutral: { dot: "bg-muted", bg: "bg-card", border: "border-border", text: "text-muted" },
  info: { dot: "bg-info", bg: "bg-info-bg", border: "border-info-border", text: "text-info" },
  success: { dot: "bg-success", bg: "bg-success-bg", border: "border-success-border", text: "text-success" },
  warning: { dot: "bg-warning", bg: "bg-warning-bg", border: "border-warning-border", text: "text-warning" },
  danger: { dot: "bg-danger", bg: "bg-danger-bg", border: "border-danger-border", text: "text-danger" },
};

function TimelineRow({ event }: { event: AuditEvent }) {
  const [showRaw, setShowRaw] = useState(false);
  const { title, tone } = describeEvent(event);
  const c = toneClasses[tone];

  return (
    <li className="relative pl-8">
      <span className={`absolute left-0 top-1.5 h-3 w-3 rounded-full ring-4 ring-background ${c.dot}`} />
      <div className={`rounded-lg border ${c.border} ${c.bg} px-3.5 py-2.5`}>
        <div className="flex items-start justify-between gap-3">
          <p className={`text-sm ${c.text} font-medium leading-snug`}>{title}</p>
          <time className="shrink-0 text-xs text-muted tabular-nums">{formatTime(event.created_at)}</time>
        </div>
        <button
          onClick={() => setShowRaw((v) => !v)}
          className="mt-1 text-xs text-muted hover:text-foreground underline decoration-dotted underline-offset-2 cursor-pointer"
        >
          {showRaw ? "hide raw event" : "view raw event"}
        </button>
        {showRaw && (
          <pre className="mt-2 overflow-x-auto rounded-md bg-black/5 dark:bg-white/5 p-2 text-[11px] leading-relaxed text-muted">
            {JSON.stringify({ event_type: event.event_type, detail: event.detail }, null, 2)}
          </pre>
        )}
      </div>
    </li>
  );
}

export default function DashboardPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchSessions();
      setSessions(data);
      setError(null);
      setSelected((prev) => prev ?? data[0]?.session_id ?? null);
    } catch {
      setError("Can't reach the backend — is it running on NEXT_PUBLIC_API_BASE_URL?");
    }
  }, []);

  useEffect(() => {
    loadSessions();
    const t = setInterval(loadSessions, SESSIONS_POLL_MS);
    return () => clearInterval(t);
  }, [loadSessions]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const load = async () => {
      try {
        const data = await fetchAuditTrail(selected);
        if (!cancelled) setEvents(data.events);
      } catch {
        /* transient poll failure — keep showing the last good state */
      }
    };
    load();
    const t = setInterval(load, EVENTS_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [selected]);

  const visibleEvents = showAll ? events : events.filter((e) => describeEvent(e).curated);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold">Merchant Audit Dashboard</h1>
          <span className="flex items-center gap-1.5 rounded-full bg-success-bg border border-success-border px-2 py-0.5 text-xs text-success">
            <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
            live
          </span>
        </div>
        <p className="text-sm text-muted mt-0.5">
          Every guardrail decision and payment event, in order, as it happens.
        </p>
      </header>

      {error && (
        <div className="mx-6 mt-4 rounded-lg border border-danger-border bg-danger-bg px-4 py-2.5 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-72 shrink-0 border-r border-border overflow-y-auto">
          {sessions.length === 0 && !error && (
            <p className="px-4 py-6 text-sm text-muted">No sessions yet — start a conversation with the buyer agent.</p>
          )}
          <ul>
            {sessions.map((s) => (
              <li key={s.session_id}>
                <button
                  onClick={() => setSelected(s.session_id)}
                  className={`w-full text-left px-4 py-3 border-b border-border transition-colors cursor-pointer ${
                    selected === s.session_id ? "bg-accent/10" : "hover:bg-black/2 dark:hover:bg-white/3"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium font-mono">{s.session_id.slice(0, 8)}</span>
                    <span className="text-xs text-muted">{s.event_count} events</span>
                  </div>
                  <span className="text-xs text-muted">{formatRelative(s.last_event_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="flex-1 overflow-y-auto px-6 py-5">
          {selected ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-muted font-mono">session {selected.slice(0, 8)}</h2>
                <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={showAll}
                    onChange={(e) => setShowAll(e.target.checked)}
                    className="accent-accent"
                  />
                  show all raw events
                </label>
              </div>
              {visibleEvents.length === 0 ? (
                <p className="text-sm text-muted">No events yet.</p>
              ) : (
                <ul className="relative space-y-3 border-l border-border ml-1.5">
                  {visibleEvents.map((e) => (
                    <TimelineRow key={e.id} event={e} />
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-sm text-muted">Select a session to view its audit trail.</p>
          )}
        </main>
      </div>
    </div>
  );
}
