import { useEffect, useState } from "react";
import { Download, FileJson, FileSpreadsheet, FileText } from "lucide-react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

const formats = [
  { key: "pdf", label: "PDF report", Icon: FileText, description: "Readable case summary for review." },
  { key: "csv", label: "CSV data", Icon: FileSpreadsheet, description: "Tabular analysis and candidate data." },
  { key: "json", label: "JSON data", Icon: FileJson, description: "Structured analysis records and metadata." },
];

export default function ReportsPage() {
  const [cases, setCases] = useState([]);
  const [caseId, setCaseId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadCases = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/cases");
      setCases(data);
      setCaseId((current) => data.some((item) => item.id === current) ? current : data[0]?.id || "");
      setError("");
    } catch (err) { setError(apiError(err, "Accessible cases could not be loaded.")); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadCases(); }, []);

  const download = async (format) => {
    if (!caseId) return;
    setBusy(format); setError(""); setMessage("");
    let objectUrl = "";
    try {
      const { data } = await api.get(`/api/cases/${caseId}/reports/${format}`, { responseType: "blob" });
      objectUrl = URL.createObjectURL(data);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `case-${cases.find((item) => item.id === caseId)?.case_identifier || caseId}-report.${format}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setMessage(`${format.toUpperCase()} report download started.`);
    } catch (err) { setError(apiError(err, `${format.toUpperCase()} report could not be generated.`)); }
    finally {
      // Keep the Blob URL alive long enough for the browser's download handler
      // to consume the clicked anchor before releasing it.
      if (objectUrl) window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setBusy("");
    }
  };

  const selected = cases.find((item) => item.id === caseId);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><p className="text-sm text-slate-500">Generate reports from actual records in cases visible to your account.</p></div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {message ? <Notice tone="success">{message}</Notice> : null}
      {loading ? <Spinner label="Loading accessible cases…" /> : null}
      {!loading && cases.length === 0 && !error ? <Notice>No accessible cases are available for report export.</Notice> : null}
      {!loading && cases.length > 0 ? <>
        <label className="block max-w-xl text-sm font-medium text-slate-700">Case
          <select className="mt-1.5 w-full rounded-lg border bg-white px-3 py-2.5" value={caseId} onChange={(event) => setCaseId(event.target.value)}>
            {cases.map((item) => <option key={item.id} value={item.id}>{item.case_identifier} · {item.imaging_modality} · {item.analysis_status}</option>)}
          </select>
        </label>
        <section className="rounded-2xl border bg-white p-5 shadow-sm lg:p-7" aria-label="Available report exports">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-semibold">Export case report</h2>
            <p className="mt-1 text-sm text-slate-500">{selected?.case_identifier} · {selected?.latest_image ? `${selected.latest_image.width ?? "?"} × ${selected.latest_image.height ?? "?"} ${selected.latest_image.format}` : "No image currently attached"}</p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {formats.map(({ key, label, Icon, description }) => (
              <article key={key} className="rounded-xl border border-slate-200 p-4">
                <Icon className="text-blue-700" size={21} aria-hidden="true" />
                <h3 className="mt-3 font-semibold">{label}</h3>
                <p className="mt-1 min-h-10 text-sm text-slate-500">{description}</p>
                <button type="button" className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-200 px-3 py-2 text-sm font-medium text-blue-800 hover:bg-blue-50 disabled:opacity-50" onClick={() => download(key)} disabled={!caseId || !!busy}>
                  <Download size={16} aria-hidden="true" />{busy === key ? "Preparing…" : "Download"}
                </button>
              </article>
            ))}
          </div>
          {selected && !selected.latest_image ? <p className="mt-4 text-xs text-amber-800">The case has no uploaded image. The backend will include only records actually stored for this case.</p> : null}
          {busy ? <div className="mt-4"><Spinner label={`Preparing ${busy.toUpperCase()} report…`} /></div> : null}
        </section>
      </> : null}
    </div>
  );
}
