import React, { useCallback, useEffect, useRef, useState } from "react";
import SearchPanel from "../components/SearchPanel.jsx";
import PipelineProgress from "../components/PipelineProgress.jsx";
import StatsCards from "../components/StatsCards.jsx";
import LeadTable from "../components/LeadTable.jsx";
import LeadDetails from "../components/LeadDetails.jsx";
import ExportButtons from "../components/ExportButtons.jsx";
import { getLeads, getStatus, getSummary, startPipeline, stopPipeline } from "./api.js";

const TERMINAL_PHASES = ["done", "stopped", "error", "idle"];

export default function App() {
  const [status, setStatus] = useState(null);
  const [leads, setLeads] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [banner, setBanner] = useState(null); // { type: 'error'|'info', message }
  const [leadsLoading, setLeadsLoading] = useState(false);
  const pollRef = useRef(null);

  const refreshLeadsAndSummary = useCallback(async () => {
    setLeadsLoading(true);
    try {
      const [leadsRes, summaryRes] = await Promise.all([getLeads(), getSummary()]);
      setLeads(leadsRes.leads || []);
      setSummary(summaryRes);
    } catch (err) {
      setBanner({ type: "error", message: `Failed to load leads: ${err.message}` });
    } finally {
      setLeadsLoading(false);
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);

      if (!TERMINAL_PHASES.includes(s.phase) || s.phase === "done") {
        // Refresh live-ish stats while running too, so grades/tables aren't empty until the very end.
      }

      if (s.running) {
        pollRef.current = setTimeout(poll, 1000);
      } else if (["done", "stopped"].includes(s.phase)) {
        await refreshLeadsAndSummary();
      }
    } catch (err) {
      setBanner({ type: "error", message: `Lost connection to backend: ${err.message}` });
    }
  }, [refreshLeadsAndSummary]);

  useEffect(() => {
    getStatus()
      .then((s) => {
        setStatus(s);
        if (s.running) {
          pollRef.current = setTimeout(poll, 1000);
        } else if (["done", "stopped"].includes(s.phase)) {
          refreshLeadsAndSummary();
        }
      })
      .catch(() => {
        setBanner({
          type: "error",
          message: "Could not reach the backend at http://127.0.0.1:8000. Is uvicorn running?",
        });
      });

    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleStart({ query, targetLeads, workers }) {
    setBanner(null);
    try {
      await startPipeline({ query, targetLeads, workers });
      setLeads([]);
      setSummary(null);
      setSelectedLead(null);
      poll();
    } catch (err) {
      setBanner({ type: "error", message: err.message });
    }
  }

  async function handleStop() {
    try {
      const res = await stopPipeline();
      setBanner({ type: "info", message: res.message });
    } catch (err) {
      setBanner({ type: "error", message: err.message });
    }
  }

  const running = !!status?.running;
  const hasLeads = leads && leads.length > 0;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          <h1>Google Maps Lead Intelligence</h1>
          <p>Discover, enrich and prioritize business leads.</p>
        </div>
      </header>

      {banner && (
        <div className={`banner banner-${banner.type}`}>
          <span>{banner.message}</span>
          <button className="banner-close" onClick={() => setBanner(null)} aria-label="Dismiss">
            ✕
          </button>
        </div>
      )}

      <main className="app-main">
        <SearchPanel onStart={handleStart} onStop={handleStop} running={running} />
        <PipelineProgress status={status} />
        <StatsCards summary={summary} />
        <ExportButtons disabled={!hasLeads} />
        <LeadTable leads={leads} onSelectLead={setSelectedLead} loading={leadsLoading} />
      </main>

      {selectedLead && <LeadDetails lead={selectedLead} onClose={() => setSelectedLead(null)} />}
    </div>
  );
}