import React from "react";

function Row({ label, value, isLink }) {
  if (!value) return null;
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      {isLink ? (
        <a className="detail-value detail-link" href={value} target="_blank" rel="noreferrer">
          {value}
        </a>
      ) : (
        <span className="detail-value">{value}</span>
      )}
    </div>
  );
}

export default function LeadDetails({ lead, onClose }) {
  if (!lead) return null;

  const socials = [
    ["Facebook", lead.facebook],
    ["Instagram", lead.instagram],
    ["LinkedIn", lead.linkedin],
    ["Twitter/X", lead.twitter],
    ["YouTube", lead.youtube],
  ].filter(([, url]) => !!url);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <h2>{lead.name || "Unnamed business"}</h2>
            <span className={`grade-badge grade-${(lead.lead_grade || "d").toLowerCase()}`}>
              {lead.lead_grade || "—"} · {lead.lead_score ?? 0}/100
            </span>
          </div>
          <button className="btn btn-ghost drawer-close" onClick={onClose} aria-label="Close details">
            ✕
          </button>
        </div>

        <div className="drawer-body">
          <section className="drawer-section">
            <h3>Overview</h3>
            <Row label="Category" value={lead.category} />
            <Row label="Rating" value={lead.rating} />
            <Row label="Review Count" value={lead.review_count} />
            <Row label="Sponsored" value={lead.is_sponsored ? "Yes" : "No"} />
          </section>

          <section className="drawer-section">
            <h3>Contact</h3>
            <Row label="Phone" value={lead.phone} />
            <Row label="Email" value={lead.email} />
            <Row label="Email Confidence" value={lead.email_confidence} />
            <Row label="Website" value={lead.website} isLink />
          </section>

          <section className="drawer-section">
            <h3>Location</h3>
            <Row label="Full Address" value={lead.full_address || lead.search_address} />
            <Row label="City" value={lead.city} />
            <Row label="Pincode" value={lead.pincode} />
            <Row label="Hours" value={lead.hours} />
          </section>

          {socials.length > 0 && (
            <section className="drawer-section">
              <h3>Social Profiles</h3>
              {socials.map(([label, url]) => (
                <Row key={label} label={label} value={url} isLink />
              ))}
            </section>
          )}

          {lead.directories && lead.directories.length > 0 && (
            <section className="drawer-section">
              <h3>Directories</h3>
              <Row label="Listed on" value={lead.directories.join(", ")} />
            </section>
          )}

          <section className="drawer-section">
            <h3>Enrichment</h3>
            <Row label="Detail Status" value={lead.detail_status} />
            <Row label="Website Status" value={lead.website_status} />
            <Row label="Pages Inspected" value={(lead.pages_inspected || []).join(", ") || "—"} />
            <Row label="Errors" value={lead.detail_error} />
          </section>

          <section className="drawer-section">
            <h3>Source</h3>
            <Row label="Maps URL" value={lead.maps_url} isLink />
          </section>
        </div>
      </aside>
    </div>
  );
}