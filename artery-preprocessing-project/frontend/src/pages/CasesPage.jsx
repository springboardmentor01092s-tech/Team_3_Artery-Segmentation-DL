import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

export default function CasesPage() {
  const [cases, setCases] = useState([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (query = "") => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/cases", { params: query ? { search: query } : {} });
      setCases(data);
      setError("");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">Cases</h2>
        <Link to="/cases/new" className="rounded-lg bg-teal-700 px-4 py-2 text-sm text-white">
          Create case
        </Link>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          load(search);
        }}
      >
        <input
          className="w-full max-w-sm rounded-lg border px-3 py-2"
          placeholder="Search by case ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="rounded-lg border px-4 py-2">Search</button>
      </form>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner /> : null}
      {!loading && !error && cases.length === 0 ? (
        <Notice>No cases are visible for your account. Create a case or ask an authorized user to share one with you.</Notice>
      ) : null}
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Case ID</th>
              <th className="px-4 py-3">Patient ID</th>
              <th className="px-4 py-3">Modality</th>
              <th className="px-4 py-3">Access</th>
              <th className="px-4 py-3">Owner</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-4 py-3">
                  <Link className="text-teal-700" to={`/cases/${item.id}`}>
                    {item.case_identifier}
                  </Link>
                </td>
                <td className="px-4 py-3">{item.patient_identifier}</td>
                <td className="px-4 py-3">{item.imaging_modality}</td>
                <td className="px-4 py-3">{item.current_access || "—"}</td>
                <td className="px-4 py-3">{item.owner_full_name || item.owner_id}</td>
                <td className="px-4 py-3">{item.analysis_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
