import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Filter, RefreshCw, Search } from "lucide-react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

const PAGE_SIZE = 25;

export default function AnalysisHistoryPage() {
  const [analyses, setAnalyses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestSequence = useRef(0);

  const load = async () => {
    const requestId = ++requestSequence.current;
    setLoading(true);
    try {
      const { data, headers } = await api.get("/api/analyses", {
        params: {
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          search: query.trim() || undefined,
          mode: mode === "all" ? undefined : mode,
        },
      });
      if (requestId !== requestSequence.current) return;
      setAnalyses(data);
      const responseTotal = Number(headers?.["x-total-count"]);
      setTotal(Number.isFinite(responseTotal) ? responseTotal : data.length);
      setError("");
    } catch (err) {
      if (requestId === requestSequence.current) setError(apiError(err, "Analysis history could not be loaded."));
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, query, mode]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Previously generated analysis records within your case-access scope.</p>
        </div>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60" onClick={load} disabled={loading}>
          <RefreshCw size={16} aria-hidden="true" /> Refresh
        </button>
      </div>

      <div className="grid gap-3 rounded-xl border bg-white p-4 shadow-sm md:grid-cols-[minmax(220px,1fr)_220px]">
        <label className="relative block text-sm text-slate-600">
          Search history
          <span className="pointer-events-none absolute bottom-[10px] left-3 text-slate-400"><Search size={16} /></span>
          <input className="mt-1 w-full rounded-lg border py-2 pl-9 pr-3" value={query} onChange={(event) => { setPage(0); setQuery(event.target.value); }} placeholder="Case, analysis ID or model" />
        </label>
        <label className="block text-sm text-slate-600">
          <span className="inline-flex items-center gap-2">Analysis mode <Filter size={14} aria-hidden="true" /></span>
          <select className="mt-1 w-full rounded-lg border px-3 py-2" value={mode} onChange={(event) => { setPage(0); setMode(event.target.value); }}>
            <option value="all">All modes</option>
            <option value="lesion">Lesion segmentation</option>
            <option value="vessel_region_experimental">Experimental vessel region</option>
          </select>
        </label>
      </div>

      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner label="Loading analysis history…" /> : null}
      {!loading && !error && analyses.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white px-6 py-12 text-center">
          <p className="font-semibold text-slate-800">{query.trim() || mode !== "all" ? "No analyses match these filters" : "No analyses yet"}</p>
          <p className="mt-1 text-sm text-slate-500">{query.trim() || mode !== "all" ? "Adjust the search or mode filter and try again." : "Run an analysis from an accessible case to create a history record."}</p>
          <Link className="mt-4 inline-flex rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800" to="/cases">Browse cases</Link>
        </div>
      ) : null}

      {!loading && analyses.length ? (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide">
                <tr><th className="px-4 py-3">Case</th><th className="px-4 py-3">Created</th><th className="px-4 py-3">Mode</th><th className="px-4 py-3">Model</th><th className="px-4 py-3">Candidates</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Details</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analyses.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3 font-medium text-slate-800">{item.case_identifier || item.case_id}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-slate-600">{item.created_at ? new Date(item.created_at).toLocaleString() : "Unavailable"}</td>
                    <td className="px-4 py-3 text-slate-600">{item.analysis_mode === "vessel_region_experimental" ? "Experimental vessel region" : "Lesion segmentation"}</td>
                    <td className="px-4 py-3 text-slate-600">{item.model_name || "Unavailable"}</td>
                    <td className="px-4 py-3 tabular-nums text-slate-600">{item.candidate_count ?? "—"}</td>
                    <td className="px-4 py-3"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">{item.status || "completed"}</span></td>
                    <td className="px-4 py-3"><Link className="font-medium text-blue-700 hover:text-blue-900" to={`/cases/${item.case_id}?analysis=${encodeURIComponent(item.id)}`}>Open analysis</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-slate-50 px-4 py-3">
            <p className="text-xs text-slate-500">Showing {page * PAGE_SIZE + 1}-{page * PAGE_SIZE + analyses.length} of {total} matching records.</p>
            <div className="flex gap-2">
              <button type="button" className="rounded-lg border bg-white px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={loading || page === 0}>Previous</button>
              <button type="button" className="rounded-lg border bg-white px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setPage((value) => value + 1)} disabled={loading || (page + 1) * PAGE_SIZE >= total}>Next</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
