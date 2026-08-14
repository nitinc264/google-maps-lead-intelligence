import React from "react";

export default function StatsCards({ summary }) {
  if (!summary || !summary.total_leads) {
    return (
      <section className="panel stats-panel">
        <p className="empty-state">Stats will appear here once leads are processed.</p>
      </section>
    );
  }

  const grades = summary.grades || {};

  return (
    <section className="panel stats-panel">
      <div className="stats-grid">
        <div className="stat-card stat-total">
          <span className="stat-value">{summary.total_leads}</span>
          <span className="stat-label">Total Leads</span>
        </div>
        <div className="stat-card grade-a">
          <span className="stat-value">{grades.A || 0}</span>
          <span className="stat-label">A · High-value</span>
        </div>
        <div className="stat-card grade-b">
          <span className="stat-value">{grades.B || 0}</span>
          <span className="stat-label">B · Good</span>
        </div>
        <div className="stat-card grade-c">
          <span className="stat-value">{grades.C || 0}</span>
          <span className="stat-label">C · Partial</span>
        </div>
        <div className="stat-card grade-d">
          <span className="stat-value">{grades.D || 0}</span>
          <span className="stat-label">D · Needs Enrichment</span>
        </div>
      </div>

      <div className="stats-grid stats-grid-secondary">
        <div className="stat-chip">
          <span className="chip-value">{summary.with_phone || 0}</span>
          <span className="chip-label">With Phone</span>
        </div>
        <div className="stat-chip">
          <span className="chip-value">{summary.with_email || 0}</span>
          <span className="chip-label">With Email</span>
        </div>
        <div className="stat-chip">
          <span className="chip-value">{summary.with_website || 0}</span>
          <span className="chip-label">With Website</span>
        </div>
        <div className="stat-chip">
          <span className="chip-value">{summary.with_social || 0}</span>
          <span className="chip-label">With Social</span>
        </div>
      </div>
    </section>
  );
}