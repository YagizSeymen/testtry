import { useEffect, useState } from "react";
import type { AuditEvent } from "@/lib/applications-data";

type AuditRow = AuditEvent & { application_id: string; company: string };

const stageColor: Record<AuditEvent["stage"], string> = {
  sourced: "var(--dim)",
  activated: "var(--signal)",
  deck_uploaded: "var(--signal)",
  claims_extracted: "var(--signal)",
  screened: "var(--contested-amber)",
  diligence: "var(--contested-amber)",
  memo: "var(--signal)",
  adversary: "var(--contested-red)",
  decision: "var(--verified)",
};

/**
 * Slide-out audit drawer. Terminal-log aesthetic — this is the one place a
 * monospace log style is appropriate because it *is* an audit trail.
 */
export function AuditDrawer({
  open,
  onClose,
  applicationId,
  title,
}: {
  open: boolean;
  onClose: () => void;
  applicationId?: string;
  title?: string;
}) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);

  useEffect(() => {
    if (!open) return;
    setRows(null);
    const q = applicationId ? `?application_id=${applicationId}` : "";
    fetch(`/api/audit${q}`)
      .then((r) => r.json())
      .then((d: { audit: AuditRow[] }) => setRows(d.audit));
  }, [open, applicationId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={
          "fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 " +
          (open ? "opacity-100" : "pointer-events-none opacity-0")
        }
      />
      {/* panel */}
      <aside
        aria-label="Audit trail"
        className={
          "fixed right-0 top-0 z-50 flex h-full w-full max-w-[560px] flex-col border-l border-[var(--ink)]/10 bg-[var(--paper)] shadow-2xl transition-transform duration-200 " +
          (open ? "translate-x-0" : "translate-x-full")
        }
      >
        <header className="flex items-center justify-between border-b border-[var(--ink)]/10 px-5 py-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              audit log
            </div>
            <h2 className="mt-0.5 font-display text-base font-medium tracking-tight text-[var(--ink)]">
              {title ?? "All applications"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm border border-[var(--ink)]/15 px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70 hover:border-[var(--ink)]/35 hover:text-[var(--ink)]"
            aria-label="Close audit drawer"
          >
            esc · close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {rows === null ? (
            <div className="font-mono text-[12px] text-[var(--ink)]/40">
              loading audit trail…
            </div>
          ) : rows.length === 0 ? (
            <div className="font-mono text-[12px] text-[var(--ink)]/45">
              no audit events recorded.
            </div>
          ) : (
            <ol className="font-mono text-[12px] leading-relaxed text-[var(--ink)]/85">
              {rows.map((r, i) => (
                <li key={i} className="group flex gap-3 border-l border-[var(--ink)]/10 pl-3 py-1.5">
                  <span className="text-[var(--ink)]/40 tabular-nums">
                    {r.at.slice(0, 19).replace("T", " ")}Z
                  </span>
                  <span
                    className="uppercase tracking-widest"
                    style={{ color: stageColor[r.stage] }}
                  >
                    {r.stage.padEnd(18, "·")}
                  </span>
                  <span
                    className="uppercase text-[10px] tracking-widest"
                    style={{
                      color:
                        r.actor === "human"
                          ? "var(--verified)"
                          : "var(--ink)/55",
                    }}
                  >
                    [{r.actor}]
                  </span>
                  <span className="min-w-0 flex-1 whitespace-pre-wrap text-[var(--ink)]/80">
                    {!applicationId && (
                      <span className="text-[var(--ink)]/45">
                        {r.application_id} · {r.company} —{" "}
                      </span>
                    )}
                    {r.note}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>

        <footer className="border-t border-[var(--ink)]/10 px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          {rows?.length ?? 0} events · newest first · immutable
        </footer>
      </aside>
    </>
  );
}
