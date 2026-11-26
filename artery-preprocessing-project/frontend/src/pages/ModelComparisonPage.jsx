import { useEffect, useState } from "react";
import { GitCompareArrows, Info } from "lucide-react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

function metric(value) { return typeof value === "number" && Number.isFinite(value) ? value.toFixed(4) : "Not evaluated"; }

export default function ModelComparisonPage() {
  const [models, setModels] = useState([]);
  const [note, setNote] = useState("");
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    Promise.all([api.get("/api/models/compare"), api.get("/api/models/info")])
      .then(([comparison, current]) => {
        if (!live) return;
        setModels(comparison.data.models || []);
        setNote(comparison.data.comparison_note || "");
        setActive(current.data);
      })
      .catch((err) => { if (live) setError(apiError(err, "Model comparison data could not be loaded.")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  return (
    <div className="space-y-6">
      <div><p className="text-sm text-slate-500">Compare checkpoint metadata and only the evaluations that are actually available.</p></div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner label="Loading checkpoint comparison…" /> : null}
      {!loading && active?.available ? (
        <section className="flex flex-wrap items-center gap-4 rounded-xl border bg-white p-5 shadow-sm" aria-label="Active checkpoint">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-800"><GitCompareArrows size={21} aria-hidden="true" /></div>
          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Active checkpoint</p><h2 className="mt-0.5 font-semibold text-slate-900">{active.active_checkpoint}</h2></div>
          <div className="ml-auto flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-blue-50 px-3 py-1.5 font-medium text-blue-800">{active.architecture || "Architecture unavailable"}</span><span className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-700">Input {active.image_size || "?"} × {active.image_size || "?"}</span><span className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-700">Threshold {active.threshold ?? "unavailable"}</span></div>
        </section>
      ) : null}
      {!loading && !error && models.length === 0 ? <Notice>No checkpoint files are available in the configured checkpoint directory.</Notice> : null}
      {!loading && models.length > 0 ? (
        <section className="overflow-hidden rounded-xl border bg-white shadow-sm" aria-label="Checkpoint comparison table">
          <div className="overflow-x-auto">
            <table className="min-w-[900px] w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Checkpoint</th><th className="px-4 py-3">Architecture</th><th className="px-4 py-3">Evaluation split / samples</th><th className="px-4 py-3">Macro Dice</th><th className="px-4 py-3">Macro IoU</th><th className="px-4 py-3">Precision</th><th className="px-4 py-3">Recall</th><th className="px-4 py-3">Threshold</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{models.map((entry) => {
                const evaluation = entry.validation_evaluation;
                const macro = evaluation?.metrics?.per_image_macro || {};
                return <tr key={entry.name} className={entry.name === active?.active_checkpoint ? "bg-blue-50/50" : ""}>
                  <td className="px-4 py-3 font-medium text-slate-800">{entry.name}{entry.name === active?.active_checkpoint ? <span className="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-blue-800">Active</span> : null}<p className="mt-1 text-xs font-normal text-slate-500">{entry.kind || "checkpoint"} · epoch {entry.epoch ?? "unavailable"}</p></td>
                  <td className="px-4 py-3 text-slate-600">{entry.resolved_architecture || "Unavailable"}<p className="mt-1 text-xs">{entry.image_size ? `${entry.image_size} px` : "Input size unavailable"}</p></td>
                  <td className="px-4 py-3 text-slate-600">{evaluation ? `${evaluation.split} · ${evaluation.samples} images` : "No saved evaluation"}</td>
                  <td className="px-4 py-3 tabular-nums">{metric(macro.dice)}</td><td className="px-4 py-3 tabular-nums">{metric(macro.iou)}</td><td className="px-4 py-3 tabular-nums">{metric(macro.precision)}</td><td className="px-4 py-3 tabular-nums">{metric(macro.recall)}</td><td className="px-4 py-3">{evaluation?.threshold ?? "Not evaluated"}</td>
                </tr>;
              })}</tbody>
            </table>
          </div>
          {note ? <div className="flex gap-2 border-t bg-slate-50 px-4 py-3 text-xs text-slate-600"><Info size={16} className="mt-0.5 flex-none text-blue-700" aria-hidden="true" /><p>{note}</p></div> : null}
        </section>
      ) : null}
      <Notice>Stored training scores and checkpoint metadata are not substituted for missing validation evaluations. These research metrics do not establish clinical performance.</Notice>
    </div>
  );
}
