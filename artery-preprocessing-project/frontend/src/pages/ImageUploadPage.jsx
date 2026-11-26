import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileUp, ImagePlus } from "lucide-react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { useAuth } from "../hooks/useAuth";
import { apiError } from "../utils/errors";

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".dcm"];

function supported(file) {
  const name = file.name.toLowerCase();
  return file.type === "image/png" || file.type === "image/jpeg" || name.endsWith(".dcm");
}

export default function ImageUploadPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [cases, setCases] = useState([]);
  const [caseId, setCaseId] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [uploaded, setUploaded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    api.get("/api/cases")
      .then(({ data }) => { if (live) { setCases(data); setCaseId(data[0]?.id || ""); } })
      .catch((err) => { if (live) setError(apiError(err, "Cases could not be loaded.")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!file) { setPreview(""); return undefined; }
    if (!file.type.startsWith("image/")) { setPreview(""); return undefined; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const chooseFile = (selected) => {
    setError(""); setUploaded(null);
    if (!selected) { setFile(null); return; }
    if (!supported(selected)) {
      setFile(null); setError("Choose a PNG, JPEG, or single-frame DICOM (.dcm) image."); return;
    }
    if (selected.size > MAX_UPLOAD_BYTES) {
      setFile(null); setError("The selected file exceeds the default 20 MiB upload limit. The backend configuration may impose a lower limit."); return;
    }
    setFile(selected);
  };

  const upload = async (event) => {
    event.preventDefault();
    if (!hasPermission("image:upload")) { setError("Your role does not have permission to upload images."); return; }
    if (!caseId || !file) return;
    setBusy(true); setError(""); setUploaded(null);
    try {
      const body = new FormData(); body.append("file", file);
      const { data } = await api.post(`/api/cases/${caseId}/upload`, body);
      setUploaded(data);
    } catch (err) {
      setError(apiError(err, "The image could not be uploaded."));
    } finally { setBusy(false); }
  };

  const selectedCase = cases.find((item) => item.id === caseId);
  const allowed = hasPermission("image:upload");

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><p className="text-sm text-slate-500">Upload a supported image to an existing case. The original is retained in protected backend storage.</p></div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner label="Loading accessible cases…" /> : null}
      {!loading && cases.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white p-10 text-center">
          <ImagePlus className="mx-auto text-blue-700" size={30} aria-hidden="true" />
          <h2 className="mt-3 text-lg font-semibold">Create a case before uploading</h2>
          <p className="mt-1 text-sm text-slate-500">Images are stored and authorized through their case.</p>
          <Link to="/cases/new" className="mt-4 inline-flex rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white">Create case</Link>
        </div>
      ) : null}
      {!loading && cases.length > 0 ? (
        <form onSubmit={upload} className="grid gap-5 rounded-2xl border bg-white p-5 shadow-sm lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,.9fr)] lg:p-7">
          <div className="space-y-5">
            <label className="block text-sm font-medium text-slate-700">Destination case
              <select className="mt-1.5 w-full rounded-lg border px-3 py-2.5" value={caseId} onChange={(event) => { setCaseId(event.target.value); setUploaded(null); }} disabled={!allowed || busy} required>
                <option value="">Select a case</option>
                {cases.map((item) => <option key={item.id} value={item.id}>{item.case_identifier} · {item.imaging_modality}</option>)}
              </select>
            </label>
            <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/40 px-5 py-8 text-center hover:border-blue-400 hover:bg-blue-50">
              <FileUp className="text-blue-700" size={30} aria-hidden="true" />
              <span className="mt-3 text-sm font-semibold text-slate-800">{file ? file.name : "Choose an image file"}</span>
              <span className="mt-1 text-xs text-slate-500">PNG, JPEG, or single-frame DICOM (.dcm) · default maximum 20 MiB</span>
              <input className="sr-only" type="file" accept={ACCEPTED_EXTENSIONS.join(",")} onChange={(event) => chooseFile(event.target.files?.[0])} disabled={!allowed || busy} />
            </label>
            {file ? <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MiB selected. Preview is local and is not sent until you submit.</p> : null}
            {!allowed ? <Notice tone="error">Your role does not have image upload permission.</Notice> : null}
            <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50" type="submit" disabled={!allowed || !caseId || !file || busy}>
              <FileUp size={16} aria-hidden="true" />{busy ? "Uploading…" : "Upload to case"}
            </button>
            {busy ? <Spinner label="Validating and saving the image…" /> : null}
            {uploaded ? <Notice tone="success">Uploaded {uploaded.original_filename} ({uploaded.width ?? "?"} × {uploaded.height ?? "?"}, {uploaded.format}). Original preserved.</Notice> : null}
            {uploaded ? <button type="button" className="text-sm font-medium text-blue-700 hover:underline" onClick={() => navigate(`/cases/${caseId}`)}>Open {selectedCase?.case_identifier || "case"}</button> : null}
          </div>
          <div className="flex min-h-64 items-center justify-center overflow-hidden rounded-xl border bg-slate-50 p-3">
            {preview ? <figure className="w-full"><img src={preview} alt="Local image preview before upload" className="mx-auto max-h-[440px] w-full object-contain" /><figcaption className="pt-2 text-center text-xs text-slate-500">Preview before upload · {file?.name}</figcaption></figure> : <p className="text-center text-sm text-slate-500">Image preview appears here for PNG and JPEG files. DICOM metadata is available after backend validation.</p>}
          </div>
        </form>
      ) : null}
    </div>
  );
}
