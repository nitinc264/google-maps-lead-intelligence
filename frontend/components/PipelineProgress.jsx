import React from "react";

const PHASES = [
  { key: "discovery", label: "Discovery", countKey: "discovered" },
  { key: "detail_enrichment", label: "Detail Enrichment", countKey: "detail_completed" },
  { key: "website_enrichment", label: "Website Enrichment", countKey: "website_completed" },
  { key: "lead_processing", label: "Lead Processing", countKey: "processed" },
];

const PHASE_ORDER = ["idle", "discovery", "detail_enrichment", "website_enrichment", "lead_processing", "done", "stopped", "error"];

function phaseState(phaseKey, currentPhase) {
  const currentIdx = PHASE_ORDER.indexOf(currentPhase);
  const thisIdx = PHASE_ORDER.indexOf(phaseKey);
  if (currentPhase === "error") return "pending";
  if (currentIdx > thisIdx || currentPhase === "done") return "complete";
  if (currentIdx === thisIdx) return "active";
  return "pending";
}

function formatElapsed(seconds) {
  const s = Math.floor(seconds || 0);
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export default function PipelineProgress({ status }) {
  if (!status) return null;

  const { phase, target, errors, elapsed_seconds } = status;
  const showCard = phase !== "idle";

  if (!showCard) {
    return (
      <section className="panel progress-panel progress-idle">
        <p className="empty-state">Run a search to see live pipeline progress here.</p>
      </section>
    );
  }

  return (
    <section className="panel progress-panel">
      <div className="panel-header">
        <h2>Pipeline Progress</h2>
        <div className="progress-meta">
          <span className={`phase-pill phase-${phase}`}>{phase.replace("_", " ")}</span>
          <span className="elapsed">⏱ {formatElapsed(elapsed_seconds)}</span>
        </div>
      </div>

      <div className="progress-stages">
        {PHASES.map((p) => {
          const count = status[p.countKey] || 0;
          const pct = target > 0 ? Math.min(100, Math.round((count / target) * 100)) : 0;
          const st = phaseState(p.key, phase);
          return (
            <div className={`stage stage-${st}`} key={p.key}>
              <div className="stage-label-row">
                <span className="stage-label">{p.label}</span>
                <span className="stage-count">
                  {count} / {target}
                </span>
              </div>
              <div className="stage-bar-track">
                <div className="stage-bar-fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {errors && errors.length > 0 && (
        <div className="progress-errors">
          <span className="errors-title">Errors ({errors.length})</span>
          <ul>
            {errors.slice(-5).map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}