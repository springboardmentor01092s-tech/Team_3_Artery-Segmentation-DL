import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";
import { ArrowRight, FolderPlus, ImagePlus } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [model, setModel] = useState(null);
  const [recent, setRecent] = useState([]);
  const [recentCases, setRecentCases] = useState([]);
  const [comparison, setComparison] = useState([]);
  const [validationExamples, setValidationExamples] = useState([]);
  const [selectedExample, setSelectedExample] = useState(null);
  const [validationPreview, setValidationPreview] = useState("");

  useEffect(() => {
    api
      .get("/api/dashboard/stats")
      .then((res) => setStats(res.data))
      .catch((err) => setError(apiError(err)));
    api.get("/api/models/info").then((res) => setModel(res.data)).catch(() => setModel({ available: false }));
    api.get("/api/analyses?limit=5").then((res) => setRecent(res.data)).catch(() => setRecent([]));
    api.get("/api/cases").then((res) => setRecentCases(res.data.slice(0, 5))).catch(() => setRecentCases([]));
    api.get("/api/models/compare").then((res) => setComparison(res.data.models || [])).catch(() => setComparison([]));
  }, []);

  useEffect(() => {
    if (!model?.available) return;
    api.get("/api/models/validation/examples")
      .then((res) => {
        setValidationExamples(res.data);
        setSelectedExample(res.data[0] || null);
      })
      .catch(() => setValidationExamples([]));
  }, [model?.available]);

  useEffect(() => {
    let live = true;
    let objectUrl = "";
    setValidationPreview("");
    if (selectedExample?.image_url) {
      api.get(selectedExample.image_url, { responseType: "blob" }).then((res) => {
        objectUrl = URL.createObjectURL(res.data);
        if (live) setValidationPreview(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      }).catch(() => { if (live) setValidationPreview(""); });
    }
    return () => { live = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [selectedExample]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!stats) return <Spinner label="Loading dashboard..." />;

  const cards = [
    ["Cases", stats.case_count],
    ["Uploaded images", stats.image_count],
    ["Preprocessing runs", stats.preprocessing_count],
    ["Failed runs", stats.failed_preprocessing_count],
    ["Completed preprocessing cases", stats.processed_case_count],
    ["Pending cases", stats.pending_case_count],
    ["Segmentation analyses", stats.segmentation_analysis_count],
  ];
  if (stats.user_count != null) cards.push(["Users", stats.user_count]);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <p className="text-sm text-slate-600">Operational overview from records visible to your account.</p>
          <div className="flex flex-wrap gap-2">
            <Link className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-3.5 py-2 text-sm font-semibold text-white hover:bg-blue-800" to="/cases/new"><FolderPlus size={16} />Create case</Link>
            <Link className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" to="/upload"><ImagePlus size={16} />Upload image</Link>
          </div>
        </div>
        <p className="mt-1 text-xs text-slate-500">Statistics are queried from the database and scoped by the backend authorization rules.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-xl border bg-white p-5">
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-semibold text-teal-800">{value}</p>
          </div>
        ))}
      </div>
      <section className="rounded-xl border bg-white p-5">
        <h3 className="font-medium">Segmentation model</h3>
        {!model ? <p className="mt-2 text-sm text-slate-500">Checking checkpoint…</p> : model.available ? (
          <>
            <p className="mt-2 text-sm text-slate-600">{model.active_checkpoint} · {model.architecture} · {model.image_size}×{model.image_size} · {model.device} · threshold {model.threshold} ({model.threshold_source}).</p>
            {model.validation ? <p className="mt-1 text-sm text-slate-600">Re-evaluated on {model.validation.samples} {model.validation.split} images: macro Dice {model.validation.metrics.per_image_macro.dice.toFixed(4)}, macro IoU {model.validation.metrics.per_image_macro.iou.toFixed(4)}.</p> : <p className="mt-1 text-sm text-slate-500">No local full-split validation report exists; stored checkpoint metrics are not treated as fresh evaluation.</p>}
          </>
        ) : <p className="mt-2 text-sm text-amber-800">Model unavailable. {model.message || "Configure the checkpoint on the backend."}</p>}
      </section>
      <section className="space-y-3 rounded-xl border bg-white p-5">
        <div><h3 className="font-medium">Ground-truth validation examples</h3>
          <p className="mt-1 text-sm text-slate-500">Each validation image compares the original, category-26 ground truth, prediction with candidate boxes, and probability heatmap.</p></div>
        {validationExamples.length === 0 ? <p className="text-sm text-slate-500">No saved validation examples are available for the active checkpoint.</p> : <>
          <div className="flex flex-wrap gap-2">{validationExamples.map((example) => <button key={example.file_name} type="button" className={`rounded-lg border px-3 py-1.5 text-sm ${selectedExample?.file_name === example.file_name ? "border-teal-700 bg-teal-50 text-teal-900" : ""}`} onClick={() => setSelectedExample(example)}>{example.label.replaceAll("_", " ")} · {example.file_name}</button>)}</div>
          {selectedExample ? <p className="text-sm text-slate-600">Validation Dice {selectedExample.metrics.dice.toFixed(3)} · ground-truth pixels {selectedExample.metrics.gt_pixels} · predicted pixels {selectedExample.metrics.pred_pixels}</p> : null}
          {validationPreview ? <img className="mx-auto w-full max-w-5xl rounded border bg-slate-100" src={validationPreview} alt={`Original, ground truth, prediction with boxes and probability heatmap for ${selectedExample.file_name}`} /> : <Spinner label="Loading protected validation comparison..." />}
        </>}
      </section>
      <section className="rounded-xl border bg-white p-5">
        <div className="flex items-center justify-between gap-3"><div><h3 className="font-semibold">Recent activity</h3><p className="mt-1 text-xs text-slate-500">Latest segmentation analysis events in your accessible cases.</p></div><Link className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-900" to="/history">View history <ArrowRight size={15} /></Link></div>
        {recent.length === 0 ? <p className="mt-2 text-sm text-slate-500">No analyses are available in your access scope.</p> : (
          <ul className="mt-3 divide-y">{recent.map((analysis) => <li key={analysis.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
            <Link className="text-teal-800 underline" to={`/cases/${analysis.case_id}`}>{analysis.case_identifier}</Link>
            <span>{new Date(analysis.created_at).toLocaleString()} · {analysis.candidate_count} candidate components · {analysis.model_name}</span>
          </li>)}</ul>
        )}
      </section>
      <section className="rounded-xl border bg-white p-5">
        <div className="flex items-center justify-between gap-3"><div><h3 className="font-semibold">Recent cases</h3><p className="mt-1 text-xs text-slate-500">Cases returned by your authorized case list.</p></div><Link className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-900" to="/cases">All cases <ArrowRight size={15} /></Link></div>
        {recentCases.length === 0 ? <p className="mt-3 text-sm text-slate-500">No cases are visible in your account.</p> : (
          <ul className="mt-3 divide-y divide-slate-100">{recentCases.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><div><Link className="font-semibold text-blue-800 hover:underline" to={`/cases/${item.id}`}>{item.case_identifier}</Link><p className="mt-0.5 text-xs text-slate-500">{item.imaging_modality} · {item.current_access || "authorized access"}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{item.analysis_status}</span></li>)}</ul>
        )}
      </section>
      <section className="rounded-xl border bg-white p-5">
        <h3 className="font-medium">Available checkpoint comparison</h3>
        {comparison.length === 0 ? <p className="mt-2 text-sm text-slate-500">No checkpoint metadata is available.</p> : <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Checkpoint</th><th className="p-2">Architecture</th><th className="p-2">Validation macro Dice</th><th className="p-2">Validation macro IoU</th><th className="p-2">Threshold</th></tr></thead><tbody>{comparison.map((entry) => { const evaluation = entry.validation_evaluation; return <tr key={entry.name} className="border-t"><td className="p-2">{entry.name}</td><td className="p-2">{entry.resolved_architecture || "unavailable"}</td><td className="p-2">{evaluation ? evaluation.metrics.per_image_macro.dice.toFixed(4) : "no evaluation"}</td><td className="p-2">{evaluation ? evaluation.metrics.per_image_macro.iou.toFixed(4) : "no evaluation"}</td><td className="p-2">{evaluation?.threshold ?? "—"}</td></tr>; })}</tbody></table></div>}
        <p className="mt-2 text-xs text-slate-500">Scores above use the full validation split and one consistent evaluation protocol. Stored training metadata is not substituted for missing evaluations.</p>
      </section>
      <Notice>{stats.disclaimer}</Notice>
    </div>
  );
}
