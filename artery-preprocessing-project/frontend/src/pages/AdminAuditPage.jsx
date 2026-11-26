import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

export default function AdminAuditPage() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/admin/audit-logs");
      setLogs(data);
      setError("");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">Audit logs</h2>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60" onClick={load} disabled={loading}>
          <RefreshCw size={15} aria-hidden="true" />{loading ? "Loading audit logs..." : "Refresh audit logs"}
        </button>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner label="Loading audit logs..." /> : null}
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Resource</th>
              <th className="px-4 py-3">Actor</th>
            </tr>
          </thead>
          <tbody>
            {!loading && !error && logs.length === 0 ? <tr><td className="px-4 py-3 text-slate-500" colSpan={4}>No audit events found.</td></tr> : null}
            {logs.map((log) => (
              <tr key={log.id} className="border-t">
                <td className="px-4 py-3">{log.created_at}</td>
                <td className="px-4 py-3">{log.action}</td>
                <td className="px-4 py-3">
                  {log.resource_type} {log.resource_id}
                </td>
                <td className="px-4 py-3">{log.actor_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
