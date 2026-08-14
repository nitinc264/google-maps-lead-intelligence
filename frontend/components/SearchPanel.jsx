import React, { useState } from "react";

export default function SearchPanel({ onStart, onStop, running }) {
  const [query, setQuery] = useState("dentists in Pune");
  const [targetLeads, setTargetLeads] = useState(20);
  const [workers, setWorkers] = useState(3);
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim()) {
      setError("Enter a search query, e.g. \"dentists in Pune\".");
      return;
    }
    if (targetLeads < 1 || targetLeads > 200) {
      setError("Target leads should be between 1 and 200.");
      return;
    }
    setError("");
    onStart({ query: query.trim(), targetLeads: Number(targetLeads), workers: Number(workers) });
  }

  return (
    <section className="panel search-panel">
      <div className="panel-header">
        <h2>Search</h2>
        <span className="panel-hint">Runs the full pipeline: discovery → enrichment → scoring</span>
      </div>

      <form className="search-form" onSubmit={handleSubmit}>
        <div className="field field-grow">
          <label htmlFor="query">Google Maps query</label>
          <input
            id="query"
            type="text"
            value={query}
            placeholder='e.g. "dentists in Pune"'
            onChange={(e) => setQuery(e.target.value)}
            disabled={running}
          />
        </div>

        <div className="field">
          <label htmlFor="targetLeads">Target leads</label>
          <input
            id="targetLeads"
            type="number"
            min={1}
            max={200}
            value={targetLeads}
            onChange={(e) => setTargetLeads(e.target.value)}
            disabled={running}
          />
        </div>

        <div className="field">
          <label htmlFor="workers">Workers</label>
          <input
            id="workers"
            type="number"
            min={1}
            max={8}
            value={workers}
            onChange={(e) => setWorkers(e.target.value)}
            disabled={running}
          />
        </div>

        <div className="field field-actions">
          {!running ? (
            <button type="submit" className="btn btn-primary">
              Start Search
            </button>
          ) : (
            <button type="button" className="btn btn-danger" onClick={onStop}>
              Stop
            </button>
          )}
        </div>
      </form>

      {error && <p className="form-error">{error}</p>}
    </section>
  );
}