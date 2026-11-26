import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";
import { useAuth } from "../hooks/useAuth";

const defaults = {
  normalize: true,
  normalize_method: "minmax",
  resize: false,
  target_width: 512,
  target_height: 512,
  preserve_aspect_ratio: true,
  denoise: false,
  denoise_method: "gaussian",
  denoise_ksize: 3,
  contrast: false,
  contrast_method: "clahe",
  clahe_clip_limit: 2,
  clahe_tile_size: 8,
};

export default function PreprocessPage() {
  const { hasPermission } = useAuth();
  const [params] = useSearchParams();
  const [cases, setCases] = useState([]);
  const [caseId, setCaseId] = useState(params.get("caseId") || "");
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState([]);
  const [config, setConfig] = useState(defaults);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loadingCases, setLoadingCases] = useState(true);
  const [loadingCase, setLoadingCase] = useState(false);
  const [latestRun, setLatestRun] = useState(null);
  const [originalUrl, setOriginalUrl] = useState("");
  const [processedUrl, setProcessedUrl] = useState("");

  const loadCases = async () => {
    const { data } = await api.get("/api/cases");
    setCases(data);
    if (!caseId && data[0]) setCaseId(data[0].id);
  };

  const loadCase = async (id) => {
    if (!id) return;
    setError("");
    setOriginalUrl("");
    setProcessedUrl("");
    const [caseRes, histRes] = await Promise.all([
      api.get(`/api/cases/${id}`),
      api.get(`/api/cases/${id}/preprocessing-history`),
    ]);
    setDetail(caseRes.data);
    setHistory(histRes.data);
    const completed = histRes.data.find((item) => item.status === "completed");
    setLatestRun(completed || histRes.data[0] || null);
    const previewErrors = [];
    if (caseRes.data.latest_image) {
      try {
        const original = await api.get(`/api/cases/${id}/image`, { responseType: "blob" });
        setOriginalUrl(URL.createObjectURL(original.data));
      } catch (err) {
        previewErrors.push(apiError(err, "Could not load the original image preview."));
      }
    }
    if (completed) {
      try {
        const processed = await api.get(`/api/cases/${id}/processed-image/${completed.id}`, { responseType: "blob" });
        setProcessedUrl(URL.createObjectURL(processed.data));
      } catch (err) {
        previewErrors.push(apiError(err, "Could not load the processed image preview."));
      }
    }
    if (previewErrors.length) setError(previewErrors.join(" "));
  };

  useEffect(() => {
    let live = true;
    loadCases().catch((err) => { if (live) setError(apiError(err)); })
      .finally(() => { if (live) setLoadingCases(false); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let live = true;
    if (caseId) setLoadingCase(true);
    loadCase(caseId).catch((err) => { if (live) setError(apiError(err)); })
      .finally(() => { if (live) setLoadingCase(false); });
    return () => { live = false; };
  }, [caseId]);

  useEffect(() => () => { if (originalUrl) URL.revokeObjectURL(originalUrl); }, [originalUrl]);
  useEffect(() => () => { if (processedUrl) URL.revokeObjectURL(processedUrl); }, [processedUrl]);

  const run = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data } = await api.post(`/api/cases/${caseId}/preprocess`, {
        ...config,
        target_width: Number(config.target_width),
        target_height: Number(config.target_height),
        denoise_ksize: Number(config.denoise_ksize),
        clahe_clip_limit: Number(config.clahe_clip_limit),
        clahe_tile_size: Number(config.clahe_tile_size),
      });
      setLatestRun(data);
      setMessage(`Preprocessing ${data.status}. Duration: ${data.duration_ms} ms.`);
      await loadCase(caseId);
    } catch (err) {
      setError(apiError(err, "Preprocessing failed."));
    } finally {
      setBusy(false);
    }
  };

  const resetView = () => {
    setProcessedUrl("");
    setConfig(defaults);
    setMessage("Display reset to the original image. Stored originals were never modified.");
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">Image preprocessing</h2>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {message ? <Notice tone="success">{message}</Notice> : null}
      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <section className="space-y-4 rounded-xl border bg-white p-5">
          <label className="block text-sm">
            Case
            <select className="mt-1 w-full rounded-lg border px-3 py-2" value={caseId} onChange={(e) => setCaseId(e.target.value)}>
              <option value="">Select a case</option>
              {cases.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.case_identifier}
                </option>
              ))}
            </select>
          </label>
          {loadingCases ? <Spinner label="Loading cases..." /> : null}
          {loadingCase ? <Spinner label="Loading case and preprocessing history..." /> : null}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={config.normalize} onChange={(e) => setConfig({ ...config, normalize: e.target.checked })} />
            Intensity normalization
          </label>
          <select
            className="w-full rounded-lg border px-3 py-2 text-sm"
            value={config.normalize_method}
            onChange={(e) => setConfig({ ...config, normalize_method: e.target.value })}
          >
            <option value="minmax">Min-max</option>
            <option value="zscore">Z-score</option>
            <option value="none">None</option>
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={config.resize} onChange={(e) => setConfig({ ...config, resize: e.target.checked })} />
            Resize
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-600">Target width
              <input aria-label="Target width" className="mt-1 w-full rounded-lg border px-3 py-2" type="number" min="1" max="4096" value={config.target_width} onChange={(e) => setConfig({ ...config, target_width: e.target.value })} disabled={!config.resize} />
            </label>
            <label className="text-xs text-slate-600">Target height
              <input aria-label="Target height" className="mt-1 w-full rounded-lg border px-3 py-2" type="number" min="1" max="4096" value={config.target_height} onChange={(e) => setConfig({ ...config, target_height: e.target.value })} disabled={!config.resize} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={config.preserve_aspect_ratio} onChange={(e) => setConfig({ ...config, preserve_aspect_ratio: e.target.checked })} />
            Preserve aspect ratio
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={config.denoise} onChange={(e) => setConfig({ ...config, denoise: e.target.checked })} />
            Noise reduction
          </label>
          <select className="w-full rounded-lg border px-3 py-2 text-sm" value={config.denoise_method} onChange={(e) => setConfig({ ...config, denoise_method: e.target.value })}>
            <option value="gaussian">Gaussian</option>
            <option value="median">Median</option>
            <option value="none">None</option>
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={config.contrast} onChange={(e) => setConfig({ ...config, contrast: e.target.checked })} />
            Contrast enhancement (CLAHE)
          </label>
          <div className="flex gap-2">
            <button className="flex-1 rounded-lg bg-blue-700 py-2 text-white disabled:opacity-60" disabled={!caseId || busy || !hasPermission("image:preprocess")} onClick={run}>
              {busy ? "Processing..." : "Start preprocessing"}
            </button>
            <button className="rounded-lg border px-3" onClick={resetView} type="button">
              Reset view
            </button>
          </div>
          {busy ? <Spinner label="Running preprocessing pipeline..." /> : null}
        </section>
        <section className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <figure className="rounded-xl border bg-white p-4">
              <figcaption className="mb-2 font-medium">Original Image</figcaption>
              {originalUrl ? <img src={originalUrl} alt="Original" className="max-h-[420px] w-full object-contain bg-slate-100" /> : <p className="text-sm text-slate-500">Upload an image on the case page first.</p>}
              {detail?.latest_image ? (
                <p className="mt-2 text-xs text-slate-500">
                  {detail.latest_image.format} · {detail.latest_image.width}×{detail.latest_image.height} · {detail.latest_image.file_size} bytes
                </p>
              ) : null}
            </figure>
            <figure className="rounded-xl border bg-white p-4">
              <figcaption className="mb-2 font-medium">Preprocessed Image</figcaption>
              {processedUrl ? <img src={processedUrl} alt="Preprocessed" className="max-h-[420px] w-full object-contain bg-slate-100" /> : <p className="text-sm text-slate-500">No processed image yet.</p>}
              {latestRun ? (
                <p className="mt-2 text-xs text-slate-500">
                  {latestRun.status} · {latestRun.processed_width ?? "—"}×{latestRun.processed_height ?? "—"} · {latestRun.duration_ms ?? "—"} ms
                </p>
              ) : null}
            </figure>
          </div>
          <div className="rounded-xl border bg-white p-4 text-sm">
            <h3 className="font-medium">Previous processing attempts</h3>
            {history.length === 0 ? <p className="mt-2 text-slate-500">None yet.</p> : null}
            <ul className="mt-2 space-y-2">
              {history.map((run) => (
                <li key={run.id} className="rounded border px-3 py-2">
                  {run.status} · {run.duration_ms ?? "—"} ms · ops: {run.operations_json}
                  {run.error_message ? <div className="text-red-700">{run.error_message}</div> : null}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
