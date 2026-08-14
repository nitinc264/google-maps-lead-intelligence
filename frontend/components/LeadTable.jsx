import React, { useMemo, useState } from "react";

const GRADE_OPTIONS = ["All", "A", "B", "C", "D"];

const RATING_OPTIONS = [
  { value: "All", label: "Rating: All" },
  { value: "4.5", label: "Rating: 4.5+" },
  { value: "4.0", label: "Rating: 4.0+" },
  { value: "3.0", label: "Rating: 3.0+" },
];

function normalizeReviewCount(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }

  const cleaned = String(value).replace(/,/g, "").trim();
  const parsed = Number(cleaned);

  return Number.isFinite(parsed) ? parsed : 0;
}

function getAreaText(lead) {
  return (
    lead.full_address ||
    lead.search_address ||
    lead.city ||
    ""
  ).toLowerCase();
}

export default function LeadTable({
  leads,
  onSelectLead,
  loading,
}) {
  const [search, setSearch] = useState("");
  const [gradeFilter, setGradeFilter] = useState("All");

  const [categoryFilter, setCategoryFilter] = useState(
    "All"
  );

  const [ratingFilter, setRatingFilter] = useState(
    "All"
  );

  const [areaFilter, setAreaFilter] = useState("");

  const [emailOnly, setEmailOnly] = useState(false);
  const [phoneOnly, setPhoneOnly] = useState(false);
  const [websiteOnly, setWebsiteOnly] = useState(false);

  const [sortDesc, setSortDesc] = useState(true);

  // ---------------------------------------------------------------------------
  // Dynamic category list
  // ---------------------------------------------------------------------------

  const categoryOptions = useMemo(() => {
    const categories = new Set();

    for (const lead of leads || []) {
      const category = (
        lead.category || ""
      ).trim();

      if (category) {
        categories.add(category);
      }
    }

    return [
      "All",
      ...Array.from(categories).sort(
        (a, b) => a.localeCompare(b)
      ),
    ];
  }, [leads]);

  // ---------------------------------------------------------------------------
  // Filtering
  // ---------------------------------------------------------------------------

  const filtered = useMemo(() => {
    let rows = leads || [];

    // Search
    if (search.trim()) {
      const q = search.trim().toLowerCase();

      rows = rows.filter(
        (lead) =>
          (lead.name || "")
            .toLowerCase()
            .includes(q) ||
          (lead.category || "")
            .toLowerCase()
            .includes(q) ||
          (
            lead.full_address ||
            lead.search_address ||
            ""
          )
            .toLowerCase()
            .includes(q) ||
          (lead.city || "")
            .toLowerCase()
            .includes(q) ||
          (lead.pincode || "")
            .toLowerCase()
            .includes(q)
      );
    }

    // Grade
    if (gradeFilter !== "All") {
      rows = rows.filter(
        (lead) =>
          lead.lead_grade === gradeFilter
      );
    }

    // Category
    if (categoryFilter !== "All") {
      rows = rows.filter(
        (lead) =>
          (lead.category || "").trim() ===
          categoryFilter
      );
    }

    // Rating
    if (ratingFilter !== "All") {
      const minimumRating = Number(
        ratingFilter
      );

      rows = rows.filter((lead) => {
        const rating = Number(
          lead.rating
        );

        return (
          Number.isFinite(rating) &&
          rating >= minimumRating
        );
      });
    }

    // Area / location text
    if (areaFilter.trim()) {
      const area = areaFilter
        .trim()
        .toLowerCase();

      rows = rows.filter((lead) =>
        getAreaText(lead).includes(area)
      );
    }

    // Contact filters
    if (emailOnly) {
      rows = rows.filter(
        (lead) => !!lead.email
      );
    }

    if (phoneOnly) {
      rows = rows.filter(
        (lead) => !!lead.phone
      );
    }

    if (websiteOnly) {
      rows = rows.filter(
        (lead) => !!lead.website
      );
    }

    // Sort by lead score
    rows = [...rows].sort(
      (a, b) =>
        sortDesc
          ? (b.lead_score || 0) -
            (a.lead_score || 0)
          : (a.lead_score || 0) -
            (b.lead_score || 0)
    );

    return rows;
  }, [
    leads,
    search,
    gradeFilter,
    categoryFilter,
    ratingFilter,
    areaFilter,
    emailOnly,
    phoneOnly,
    websiteOnly,
    sortDesc,
  ]);

  return (
    <section className="panel table-panel">
      <div className="panel-header">
        <h2>Leads</h2>

        <span className="panel-hint">
          {filtered.length} shown of{" "}
          {(leads || []).length}
        </span>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* FILTERS                                                             */}
      {/* ------------------------------------------------------------------- */}

      <div className="table-filters">
        {/* Search */}
        <input
          type="text"
          className="table-search"
          placeholder="Search name, category, address…"
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
        />

        {/* Grade */}
        <select
          value={gradeFilter}
          onChange={(event) =>
            setGradeFilter(
              event.target.value
            )
          }
        >
          {GRADE_OPTIONS.map((grade) => (
            <option
              key={grade}
              value={grade}
            >
              Grade: {grade}
            </option>
          ))}
        </select>

        {/* Category */}
        <select
          value={categoryFilter}
          onChange={(event) =>
            setCategoryFilter(
              event.target.value
            )
          }
        >
          {categoryOptions.map(
            (category) => (
              <option
                key={category}
                value={category}
              >
                Category: {category}
              </option>
            )
          )}
        </select>

        {/* Rating */}
        <select
          value={ratingFilter}
          onChange={(event) =>
            setRatingFilter(
              event.target.value
            )
          }
        >
          {RATING_OPTIONS.map(
            (option) => (
              <option
                key={option.value}
                value={option.value}
              >
                {option.label}
              </option>
            )
          )}
        </select>

        {/* Area */}
        <input
          type="text"
          className="area-filter"
          placeholder="Area / locality…"
          value={areaFilter}
          onChange={(event) =>
            setAreaFilter(
              event.target.value
            )
          }
        />

        {/* Email */}
        <label className="filter-toggle">
          <input
            type="checkbox"
            checked={emailOnly}
            onChange={(event) =>
              setEmailOnly(
                event.target.checked
              )
            }
          />
          Has Email
        </label>

        {/* Phone */}
        <label className="filter-toggle">
          <input
            type="checkbox"
            checked={phoneOnly}
            onChange={(event) =>
              setPhoneOnly(
                event.target.checked
              )
            }
          />
          Has Phone
        </label>

        {/* Website */}
        <label className="filter-toggle">
          <input
            type="checkbox"
            checked={websiteOnly}
            onChange={(event) =>
              setWebsiteOnly(
                event.target.checked
              )
            }
          />
          Has Website
        </label>

        {/* Sort */}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() =>
            setSortDesc(
              (current) => !current
            )
          }
        >
          Score {sortDesc ? "↓" : "↑"}
        </button>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* TABLE                                                               */}
      {/* ------------------------------------------------------------------- */}

      <div className="table-wrap">
        {loading ? (
          <p className="empty-state">
            Loading leads…
          </p>
        ) : filtered.length === 0 ? (
          <p className="empty-state">
            {(leads || []).length === 0
              ? "No leads yet. Run a search to discover businesses."
              : "No leads match the current filters."}
          </p>
        ) : (
          <table className="lead-table">
            <thead>
              <tr>
                <th>Business</th>
                <th>Category</th>
                <th>Phone</th>
                <th>Email</th>
                <th>Rating</th>
                <th>Reviews</th>
                <th>Score</th>
                <th>Grade</th>
                <th>Website</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map((lead) => (
                <tr
                  key={lead.lead_id}
                  onClick={() =>
                    onSelectLead(lead)
                  }
                  className="lead-row"
                >
                  <td className="cell-name">
                    {lead.name || "—"}
                  </td>

                  <td>
                    {lead.category || "—"}
                  </td>

                  <td>
                    {lead.phone || "—"}
                  </td>

                  <td>
                    {lead.email || "—"}
                  </td>

                  <td>
                    {lead.rating || "—"}
                  </td>

                  <td>
                    {normalizeReviewCount(
                      lead.review_count
                    ) > 0
                      ? Number(
                          normalizeReviewCount(
                            lead.review_count
                          )
                        ).toLocaleString()
                      : "—"}
                  </td>

                  <td>
                    {lead.lead_score ??
                      "—"}
                  </td>

                  <td>
                    <span
                      className={`grade-badge grade-${(
                        lead.lead_grade ||
                        "d"
                      ).toLowerCase()}`}
                    >
                      {lead.lead_grade ||
                        "—"}
                    </span>
                  </td>

                  <td>
                    {lead.website
                      ? "Yes"
                      : "No"}
                  </td>

                  <td className="cell-status">
                    {lead.website_status ||
                      lead.detail_status ||
                      "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}