import React from "react";
import { downloadCSV, downloadExcel, downloadJSON } from "../src/api.js";

export default function ExportButtons({ disabled }) {
  return (
    <section className="panel export-panel">
      <div className="panel-header">
        <h2>Export</h2>
        <span className="panel-hint">Download the current results</span>
      </div>
      <div className="export-buttons">
        <button className="btn btn-secondary" disabled={disabled} onClick={downloadCSV}>
          Export CSV
        </button>
        <button className="btn btn-secondary" disabled={disabled} onClick={downloadExcel}>
          Export Excel
        </button>
        <button className="btn btn-secondary" disabled={disabled} onClick={downloadJSON}>
          Export JSON
        </button>
      </div>
    </section>
  );
}