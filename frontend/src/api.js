const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

/**
 * Generic API request helper.
 */
async function apiRequest(endpoint, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    throw new Error(
      `Could not reach backend at ${API_BASE_URL}. Is FastAPI running?`
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;

    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // Keep default error message.
    }

    throw new Error(detail);
  }

  return response.json();
}


/**
 * Start the complete lead-generation pipeline.
 *
 * App.jsx sends:
 * {
 *   query,
 *   targetLeads,
 *   workers
 * }
 */
export async function startPipeline({
  query,
  targetLeads = 20,
  workers = 3,
}) {
  if (!query || !query.trim()) {
    throw new Error("Search query is required.");
  }

  return apiRequest("/api/run", {
    method: "POST",
    body: JSON.stringify({
      query: query.trim(),
      target_leads: Number(targetLeads),
      workers: Number(workers),
    }),
  });
}


/**
 * Get current pipeline status.
 */
export async function getStatus() {
  return apiRequest("/api/status");
}


/**
 * Get processed/current leads.
 *
 * Note:
 * The current LeadTable performs its filtering locally,
 * but these query parameters are still supported here for
 * future backend-side filtering.
 */
export async function getLeads(filters = {}) {
  const params = new URLSearchParams();

  if (filters.search) {
    params.set("search", filters.search);
  }

  if (filters.grade && filters.grade !== "All") {
    params.set("grade", filters.grade);
  }

  if (filters.has_email === true) {
    params.set("has_email", "true");
  }

  if (filters.has_phone === true) {
    params.set("has_phone", "true");
  }

  if (filters.has_website === true) {
    params.set("has_website", "true");
  }

  const queryString = params.toString();

  return apiRequest(
    `/api/leads${queryString ? `?${queryString}` : ""}`
  );
}


/**
 * Get summary statistics.
 */
export async function getSummary() {
  return apiRequest("/api/summary");
}


/**
 * Get a single lead by ID.
 */
export async function getLead(leadId) {
  if (leadId === undefined || leadId === null || leadId === "") {
    throw new Error("Lead ID is required.");
  }

  return apiRequest(
    `/api/leads/${encodeURIComponent(leadId)}`
  );
}


/**
 * Stop the currently running pipeline.
 */
export async function stopPipeline() {
  return apiRequest("/api/stop", {
    method: "POST",
  });
}


/**
 * Download a generated export file.
 */
async function downloadExport(format) {
  const endpointMap = {
    csv: "/api/export/csv",
    excel: "/api/export/excel",
    json: "/api/export/json",
  };

  const filenameMap = {
    csv: "leads.csv",
    excel: "leads.xlsx",
    json: "leads.json",
  };

  const endpoint = endpointMap[format];

  if (!endpoint) {
    throw new Error(`Unsupported export format: ${format}`);
  }

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`);
  } catch {
    throw new Error(
      `Could not reach backend at ${API_BASE_URL}. Is FastAPI running?`
    );
  }

  if (!response.ok) {
    let detail = `Export failed with status ${response.status}`;

    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // Keep default error.
    }

    throw new Error(detail);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filenameMap[format];

  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  window.URL.revokeObjectURL(url);

  return {
    success: true,
    filename: filenameMap[format],
  };
}


/**
 * Download CSV.
 */
export async function downloadCSV() {
  return downloadExport("csv");
}


/**
 * Download Excel.
 */
export async function downloadExcel() {
  return downloadExport("excel");
}


/**
 * Download JSON.
 */
export async function downloadJSON() {
  return downloadExport("json");
}


/**
 * Backend health check.
 */
export async function checkBackendHealth() {
  return apiRequest("/");
}