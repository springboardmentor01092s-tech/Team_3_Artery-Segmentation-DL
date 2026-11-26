import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { useAuth } from "../hooks/useAuth";
import { apiError } from "../utils/errors";

export default function CaseDetailPage() {
  const { caseId } = useParams();
  const [searchParams] = useSearchParams();
  const selectedAnalysisId = searchParams.get("analysis");
  const navigate = useNavigate();
  const { user, hasPermission } = useAuth();
  const [item, setItem] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [notes, setNotes] = useState("");
  const [metadata, setMetadata] = useState({});
  const [candidates, setCandidates] = useState([]);
  const [grants, setGrants] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [accessType, setAccessType] = useState("shared");
  const [accessBusy, setAccessBusy] = useState(false);
  const [accessLoading, setAccessLoading] = useState(false);
  const [analyses, setAnalyses] = useState([]);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [explanationBusyId, setExplanationBusyId] = useState("");
  const [groundTruthBusyId, setGroundTruthBusyId] = useState("");
  const [analysisMode, setAnalysisMode] = useState("lesion");
  const [artifactUrls, setArtifactUrls] = useState({});
  const [originalUrl, setOriginalUrl] = useState("");

  const load = async () => {
    setError("");
    try {
      const [caseRes, histRes, analysisRes] = await Promise.all([
        api.get(`/api/cases/${caseId}`),
        api.get(`/api/cases/${caseId}/preprocessing-history`),
        api.get(`/api/cases/${caseId}/analyses`),
      ]);
      setItem(caseRes.data);
      setNotes(caseRes.data.clinical_notes || "");
      setMetadata({ patient_identifier: caseRes.data.patient_identifier || "", age: caseRes.data.age ?? "",
        gender: caseRes.data.gender || "", imaging_modality: caseRes.data.imaging_modality || "",
        anatomical_region: caseRes.data.anatomical_region || "", scan_date: caseRes.data.scan_date || "",
        medical_history: caseRes.data.medical_history || "", risk_factors: caseRes.data.risk_factors || "" });
      setHistory(histRes.data);
      setAnalyses(analysisRes.data);
      if (Array.isArray(caseRes.data.access_grants)) {
        setAccessLoading(true);
        try {
          const [grantRes, candidateRes] = await Promise.all([
            api.get(`/api/cases/${caseId}/access`),
            api.get(`/api/cases/${caseId}/access-candidates`),
          ]);
          setGrants(grantRes.data);
          setCandidates(candidateRes.data);
          setSelectedUserId(candidateRes.data[0]?.id || "");
        } catch (accessErr) {
          setGrants(caseRes.data.access_grants);
          setError(apiError(accessErr));
        } finally {
          setAccessLoading(false);
        }
      } else {
        setGrants([]);
        setCandidates([]);
      }
    } catch (err) {
      setError(apiError(err));
    }
  };

  useEffect(() => {
    load();
  }, [caseId]);

  useEffect(() => {
    if (!selectedAnalysisId) return;
    const selected = document.getElementById(`analysis-${selectedAnalysisId}`);
    selected?.scrollIntoView?.({ block: "start" });
    selected?.focus?.();
  }, [selectedAnalysisId, analyses]);

  useEffect(() => {
    let live = true;
    const loadArtifacts = async () => {
      const entries = await Promise.all(analyses.map(async (analysis) => {
        const urls = {};
        await Promise.all(Object.entries(analysis.artifacts || {}).map(async ([name, path]) => {
          try {
            const response = await api.get(path, { responseType: "blob" });
            urls[name] = URL.createObjectURL(response.data);
          } catch { /* A missing old artifact leaves its preview unavailable. */ }
        }));
        return [analysis.id, urls];
      }));
      if (!live) {
        entries.forEach(([, urls]) => Object.values(urls).forEach(URL.revokeObjectURL));
        return;
      }
      setArtifactUrls((previous) => {
        Object.values(previous).forEach((urls) => Object.values(urls).forEach(URL.revokeObjectURL));
        return Object.fromEntries(entries);
      });
    };
    if (analyses.length) loadArtifacts();
    else setArtifactUrls({});
    return () => { live = false; };
  }, [analyses]);

  useEffect(() => {
    let live = true;
    let objectUrl = "";
    if (item?.latest_image?.id) {
      api.get(`/api/cases/${caseId}/image`, { responseType: "blob" }).then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        if (live) setOriginalUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      }).catch(() => { if (live) setOriginalUrl(""); });
    } else setOriginalUrl("");
    return () => { live = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [caseId, item?.latest_image?.id]);

  const runAnalysis = async () => {
    setAnalysisBusy(true); setError(""); setMessage("");
    try {
      const path = `/api/cases/${caseId}/analyze${analysisMode === "lesion" ? "" : `?mode=${analysisMode}`}`;
      await api.post(path);
      setMessage(analysisMode === "lesion"
        ? "Lesion-region analysis completed. Review the model output as research data only."
        : "Experimental SYNTAX vessel-region analysis completed. Pixel widths are not lumen measurements.");
      await load();
    } catch (err) { setError(apiError(err, "Segmentation analysis failed.")); }
    finally { setAnalysisBusy(false); }
  };

  const generateExplanation = async (analysisId) => {
    setExplanationBusyId(analysisId); setError(""); setMessage("");
    try {
      await api.post(`/api/analyses/${analysisId}/explain`);
      setMessage("Integrated Gradients attribution generated. It describes model input sensitivity and is not clinical evidence.");
      await load();
    } catch (err) { setError(apiError(err, "Model attribution could not be generated.")); }
    finally { setExplanationBusyId(""); }
  };

  const compareGroundTruth = async (analysisId) => {
    setGroundTruthBusyId(analysisId); setError(""); setMessage("");
    try {
      await api.post(`/api/analyses/${analysisId}/ground-truth`);
      setMessage("Existing prediction compared with an exact ARCADE training annotation. Pixel overlap is not a clinical stenosis measurement.");
      await load();
    } catch (err) { setError(apiError(err, "ARCADE ground-truth comparison could not be completed.")); }
    finally { setGroundTruthBusyId(""); }
  };

  const exportReport = async (format) => {
    try {
      const response = await api.get(`/api/cases/${caseId}/reports/${format}`, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `case-${item.case_identifier}-report.${format}`;
      anchor.click(); URL.revokeObjectURL(url);
    } catch (err) { setError(apiError(err, "Report export failed.")); }
  };

  const upload = async (selected) => {
    if (!selected) return;
    setUploading(true);
    setError("");
    setMessage("");
    const form = new FormData();
    form.append("file", selected);
    try {
      await api.post(`/api/cases/${caseId}/upload`, form);
      setMessage("Image uploaded. The original file is stored unchanged.");
      setFile(null);
      await load();
    } catch (err) {
      setError(apiError(err, "Upload failed."));
    } finally {
      setUploading(false);
    }
  };

  const saveNotes = async () => {
    try {
      await api.patch(`/api/cases/${caseId}`, { ...metadata, age: metadata.age === "" ? null : Number(metadata.age),
        scan_date: metadata.scan_date || null, clinical_notes: notes });
      setMessage("Case metadata updated.");
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  };

  const remove = async () => {
    if (!window.confirm("Delete this case and its stored images? This cannot be undone.")) return;
    try {
      await api.delete(`/api/cases/${caseId}`);
      navigate("/cases");
    } catch (err) {
      setError(apiError(err));
    }
  };

  const grantAccess = async () => {
    if (!selectedUserId) return;
    setAccessBusy(true);
    setError("");
    setMessage("");
    try {
      await api.post(`/api/cases/${caseId}/access`, { user_id: selectedUserId, access_type: accessType });
      setMessage("Case access granted.");
      await load();
    } catch (err) {
      setError(apiError(err, "Unable to grant access."));
    } finally {
      setAccessBusy(false);
    }
  };

  const revokeAccess = async (grantId) => {
    setAccessBusy(true);
    setError("");
    setMessage("");
    try {
      await api.delete(`/api/cases/${caseId}/access/${grantId}`);
      setMessage("Case access revoked.");
      await load();
    } catch (err) {
      setError(apiError(err, "Unable to revoke access."));
    } finally {
      setAccessBusy(false);
    }
  };

  const canMutate = item?.current_access === "owner" || user?.role === "administrator";
  const canManageAccess = Array.isArray(item?.access_grants);
  const canAssign = hasPermission("case:assign");
  const canShare = hasPermission("case:share");

  if (!item && !error) return <Spinner label="Loading case..." />;
  if (error && !item) return <Notice tone="error">{error}</Notice>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">{item.case_identifier}</h2>
          <p className="text-sm text-slate-500">Status: {item.analysis_status}</p>
          <p className="text-sm text-slate-500">
            Access: {item.current_access || "—"} · Owner: {item.owner_full_name || item.owner_id}
          </p>
        </div>
        <div className="flex gap-2">
          <Link className="rounded-lg bg-teal-700 px-4 py-2 text-sm text-white" to={`/preprocess?caseId=${item.id}`}>
            Open preprocessing
          </Link>
          {canMutate ? (
            <button className="rounded-lg border border-red-300 px-4 py-2 text-sm text-red-700" onClick={remove}>
              Delete case
            </button>
          ) : null}
        </div>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {message ? <Notice tone="success">{message}</Notice> : null}
      <section className="grid gap-4 rounded-xl border bg-white p-5 md:grid-cols-2">
        <p><span className="text-slate-500">Patient ID:</span> {item.patient_identifier}</p>
        <p><span className="text-slate-500">Age:</span> {item.age ?? "—"}</p>
        <p><span className="text-slate-500">Gender:</span> {item.gender ?? "—"}</p>
        <p><span className="text-slate-500">Modality:</span> {item.imaging_modality}</p>
        <p><span className="text-slate-500">Scan date:</span> {item.scan_date ?? "—"}</p>
        <p><span className="text-slate-500">Region:</span> {item.anatomical_region ?? "—"}</p>
        <p className="md:col-span-2"><span className="text-slate-500">History:</span> {item.medical_history || "—"}</p>
        <p className="md:col-span-2"><span className="text-slate-500">Risk factors:</span> {item.risk_factors || "—"}</p>
      </section>
      <section className="rounded-xl border bg-white p-5">
        <h3 className="font-medium">Case details and clinical notes</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {[["patient_identifier", "Patient ID"], ["age", "Age"], ["gender", "Gender"], ["imaging_modality", "Modality"], ["anatomical_region", "Region"], ["scan_date", "Scan date"]].map(([field, label]) => <label key={field} className="text-sm">{label}<input className="mt-1 block w-full rounded-lg border px-3 py-2" type={field === "scan_date" ? "date" : field === "age" ? "number" : "text"} value={metadata[field] ?? ""} disabled={!canMutate} onChange={(e) => setMetadata({ ...metadata, [field]: e.target.value })} /></label>)}
          <label className="text-sm sm:col-span-2">Medical history<textarea className="mt-1 block w-full rounded-lg border px-3 py-2" value={metadata.medical_history || ""} disabled={!canMutate} onChange={(e) => setMetadata({ ...metadata, medical_history: e.target.value })} /></label>
          <label className="text-sm sm:col-span-2">Risk factors<textarea className="mt-1 block w-full rounded-lg border px-3 py-2" value={metadata.risk_factors || ""} disabled={!canMutate} onChange={(e) => setMetadata({ ...metadata, risk_factors: e.target.value })} /></label>
        </div>
        <label className="mt-3 block text-sm">Clinical notes</label>
        <textarea
          className="mt-2 w-full rounded-lg border px-3 py-2"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={!canMutate}
        />
        {canMutate ? (
          <button className="mt-3 rounded-lg border px-4 py-2" onClick={saveNotes}>
            Save case details
          </button>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Only the owner or an administrator can update case metadata.</p>
        )}
      </section>
      {canManageAccess ? (
        <section className="rounded-xl border bg-white p-5">
          <h3 className="font-medium">Assignment and sharing</h3>
          <p className="mt-1 text-sm text-slate-500">
            Grant access to an existing active account. Assigned and shared users can view this case and its images; they
            cannot see other private cases.
          </p>
          {accessLoading ? <Spinner label="Loading access..." /> : null}
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="text-sm">
              User
              <select
                className="mt-1 block min-w-56 rounded-lg border px-3 py-2"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
              >
                {candidates.length === 0 ? <option value="">No eligible users</option> : null}
                {candidates.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.full_name} ({candidate.email}) · {candidate.role}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Access type
              <select
                className="mt-1 block rounded-lg border px-3 py-2"
                value={accessType}
                onChange={(e) => setAccessType(e.target.value)}
              >
                {canShare ? <option value="shared">shared</option> : null}
                {canAssign ? <option value="assigned">assigned</option> : null}
              </select>
            </label>
            <button
              className="rounded-lg bg-teal-700 px-4 py-2 text-sm text-white disabled:opacity-60"
              disabled={!selectedUserId || accessBusy || (!canShare && !canAssign)}
              onClick={grantAccess}
            >
              {accessBusy ? "Saving..." : "Grant access"}
            </button>
          </div>
          {grants.length === 0 && !accessLoading ? (
            <Notice>No assignment or sharing grants yet.</Notice>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {grants.map((grant) => (
                <li key={grant.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2">
                  <span>
                    {grant.user_full_name || grant.user_id} · {grant.user_email} · {grant.access_type}
                  </span>
                  <button className="rounded-lg border px-3 py-1 text-red-700" onClick={() => revokeAccess(grant.id)}>
                    Revoke
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      <section className="rounded-xl border bg-white p-5">
        <h3 className="font-medium">Image upload</h3>
        <p className="mt-1 text-sm text-slate-500">PNG, JPEG, or single-frame DICOM. Files are stored outside the public frontend directory.</p>
        <div
          className="mt-3 rounded-lg border border-dashed px-4 py-8 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const dropped = e.dataTransfer.files[0];
            setFile(dropped);
            upload(dropped);
          }}
        >
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.dcm,.dicom,image/png,image/jpeg"
            onChange={(e) => {
              const selected = e.target.files[0];
              setFile(selected);
            }}
          />
          {file ? (
            <p className="mt-2 text-sm">
              {file.name} ({Math.round(file.size / 1024)} KB)
            </p>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Choose a file or drop it here.</p>
          )}
        </div>
        <button
          className="mt-3 rounded-lg bg-teal-700 px-4 py-2 text-white disabled:opacity-60"
          disabled={!file || uploading}
          onClick={() => upload(file)}
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
        {item.latest_image ? (
          <p className="mt-3 text-sm">
            Current image: {item.latest_image.original_filename} · {item.latest_image.format} ·{" "}
            {item.latest_image.width}×{item.latest_image.height} · {item.latest_image.file_size} bytes
          </p>
        ) : null}
      </section>
      <section className="rounded-xl border bg-white p-5">
        <h3 className="font-medium">Preprocessing history</h3>
        {history.length === 0 ? <p className="mt-2 text-sm text-slate-500">No preprocessing attempts yet.</p> : null}
        <ul className="mt-3 space-y-2 text-sm">
          {history.map((run) => (
            <li key={run.id} className="rounded-lg border px-3 py-2">
              <strong>{run.status}</strong> · {run.duration_ms ?? "—"} ms · {run.input_format} ·{" "}
              {run.original_width}×{run.original_height} → {run.processed_width ?? "—"}×{run.processed_height ?? "—"}
              {run.error_message ? <div className="text-red-700">{run.error_message}</div> : null}
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-4 rounded-xl border bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="font-medium">Segmentation analysis</h3>
            <p className="mt-1 text-sm text-slate-500">Lesion analysis is the default. SYNTAX mode is experimental vessel-region segmentation, not a stenosis diagnosis.</p></div>
          <div className="flex flex-wrap gap-2">
            <label className="grid gap-1 text-xs text-slate-600">Analysis mode
              <select aria-label="Analysis mode" className="rounded border bg-white px-2 py-2 text-sm" value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value)} disabled={analysisBusy}>
                <option value="lesion">Lesion candidates (default)</option>
                <option value="vessel_region_experimental">Experimental vessel-region</option>
              </select>
            </label>
            <button className="self-end rounded-lg bg-teal-700 px-4 py-2 text-sm text-white disabled:opacity-60" onClick={runAnalysis} disabled={!item.latest_image || analysisBusy || !hasPermission("image:preprocess")}>
              {analysisBusy ? "Analyzing…" : `Run ${analysisMode === "lesion" ? "lesion" : "experimental vessel-region"} analysis`}
            </button>
            {item.latest_image ? <>
              <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportReport("pdf")}>PDF</button>
              <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportReport("csv")}>CSV</button>
              <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => exportReport("json")}>JSON</button>
            </> : null}
          </div>
        </div>
        {originalUrl ? <figure className="max-w-md"><img className="w-full rounded border bg-slate-100" src={originalUrl} alt="Original uploaded source image" /><figcaption className="mt-1 text-xs text-slate-500">Original uploaded image (unchanged)</figcaption></figure> : null}
        {analyses.length === 0 ? <p className="text-sm text-slate-500">No segmentation analyses recorded.</p> : null}
        {analyses.length > 0 && selectedAnalysisId && !analyses.some((analysis) => analysis.id === selectedAnalysisId) ? <Notice tone="error">The selected analysis was not found in this case.</Notice> : null}
        {(selectedAnalysisId ? analyses.filter((analysis) => analysis.id === selectedAnalysisId) : analyses).map((analysis) => (
          <article id={`analysis-${analysis.id}`} tabIndex={-1} key={analysis.id} className={`rounded-lg border p-4 ${analysis.id === selectedAnalysisId ? "border-blue-400 bg-blue-50/40 ring-2 ring-blue-100" : ""}`}>
            <div className="flex flex-wrap justify-between gap-2 text-sm">
              <strong>{new Date(analysis.created_at).toLocaleString()}</strong><span>{analysis.analysis_mode === "vessel_region_experimental" ? "EXPERIMENTAL VESSEL-REGION" : "LESION REGION"} · {analysis.model_name} · {analysis.model?.architecture || "unknown architecture"} · {analysis.model?.image_size || "?"}×{analysis.model?.image_size || "?"} input · {analysis.analysis_mode === "vessel_region_experimental" ? `${analysis.region_component_count || 0} vessel-region components` : `${analysis.candidate_count} candidate components`}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">Target: {analysis.target_semantics || "category-26 lesion-region mask"}. Foreground pixels: {analysis.foreground_pixels}. Threshold: {analysis.threshold}.</p>
            {analysis.analysis_mode !== "vessel_region_experimental" ? <div className="mt-3">
              <button className="rounded-lg border px-3 py-2 text-sm disabled:opacity-60" onClick={() => generateExplanation(analysis.id)} disabled={!!explanationBusyId || !hasPermission("image:preprocess")}>
                {explanationBusyId === analysis.id ? "Generating attribution…" : analysis.explainability ? "Regenerate Integrated Gradients attribution" : "Generate Integrated Gradients attribution"}
              </button>
              {analysis.explainability ? <p className="mt-1 text-xs text-slate-600">{analysis.explainability.method} · {analysis.explainability.steps} steps. {analysis.explainability.interpretation}</p> : null}
              {!analysis.checkpoint_sha256 ? <p className="mt-1 text-xs text-slate-500">Legacy analysis: original checkpoint identity was not recorded, so same-model attribution is unavailable.</p> : null}
            </div> : null}
            {analysis.analysis_mode !== "vessel_region_experimental" && hasPermission("dataset:inspect") ? <div className="mt-2">
              <button className="rounded-lg border px-3 py-2 text-sm disabled:opacity-60" onClick={() => compareGroundTruth(analysis.id)} disabled={!!groundTruthBusyId}>
                {groundTruthBusyId === analysis.id ? "Comparing with ARCADE labels…" : analysis.ground_truth_comparison ? "Refresh ARCADE ground-truth comparison" : "Compare with ARCADE train ground truth"}
              </button>
            </div> : null}
            {analysis.ground_truth_comparison ? <section aria-label="ARCADE ground-truth comparison" className="mt-3 rounded border bg-emerald-50 p-3 text-sm text-emerald-950">
              <h4 className="font-medium">ARCADE lesion-label comparison</h4>
              <p className="mt-1">{analysis.ground_truth_comparison.dataset_split} · image ID {analysis.ground_truth_comparison.image_id} · annotation IDs {analysis.ground_truth_comparison.annotation_ids.join(", ")} · category {analysis.ground_truth_comparison.category_ids.join(", ")} · {analysis.ground_truth_comparison.width}×{analysis.ground_truth_comparison.height} · exact image alignment {analysis.ground_truth_comparison.alignment_verified ? "verified" : "not verified"}.</p>
              <p className="mt-1">Dice {analysis.ground_truth_comparison.metrics.dice.toFixed(4)} · IoU {analysis.ground_truth_comparison.metrics.iou.toFixed(4)} · precision {analysis.ground_truth_comparison.metrics.precision.toFixed(4)} · recall {analysis.ground_truth_comparison.metrics.recall.toFixed(4)} · TP {analysis.ground_truth_comparison.metrics.tp} · FP {analysis.ground_truth_comparison.metrics.fp} · FN {analysis.ground_truth_comparison.metrics.fn}.</p>
              <ul className="mt-2 grid gap-1 sm:grid-cols-2">{analysis.ground_truth_comparison.predicted_components.map((component) => <li key={component.candidate_id}>Candidate {component.candidate_id}: {component.overlaps_ground_truth ? "overlaps" : "does not overlap"} the annotation ({component.ground_truth_overlap_pixels} overlap pixels; {component.predicted_pixels} predicted pixels).</li>)}</ul>
              <p className="mt-2 text-xs">{analysis.ground_truth_comparison.metrics_semantics} Checkpoint identity {analysis.ground_truth_comparison.checkpoint_matches_current ? "matches the current checkpoint" : analysis.ground_truth_comparison.checkpoint_identity_verified ? "was recorded but does not match the current checkpoint" : "was not recorded for this historical analysis"}.</p>
            </section> : null}
            {analysis.analysis_mode === "vessel_region_experimental" ? <section aria-label="Experimental vessel-region widths" className="mt-3 rounded border bg-blue-50 p-3 text-sm text-blue-950">
              <h4 className="font-medium">Experimental vessel-region width estimates</h4>
              <p>Pixel-only widths from local centerline normals. These are not lumen diameters and are not used to calculate stenosis percentage.</p>
              <p className="mt-1">Smallest sampled width: {analysis.minimum_estimated_vessel_region_width_px == null ? "Unable to estimate" : `${analysis.minimum_estimated_vessel_region_width_px} px`}. Valid cross-sections: {analysis.width_measurements?.length || 0}.</p>
              {!!analysis.width_measurements?.length && <ul className="mt-2 grid gap-1 sm:grid-cols-2">{analysis.width_measurements.slice(0, 12).map((item, index) => <li key={`${item.x}-${item.y}-${index}`}>Section {index + 1}: {item.width_px} px at ({item.x}, {item.y}), axis {item.vessel_axis_angle_degrees} deg.</li>)}</ul>}
              <p className="mt-2 text-xs">{(analysis.width_quality_notes || []).join(" ")} No clinical severity or narrowing percentage is reported.</p>
            </section> : null}
            <section aria-label="Diameter-based stenosis measurement" className="mt-3 rounded border bg-amber-50 p-3 text-sm text-amber-950">
              <h4 className="font-medium">Diameter-based stenosis measurement</h4>
              <dl className="mt-2 grid gap-1 sm:grid-cols-2">
                <div><dt className="inline font-medium">Reference vessel diameter: </dt><dd className="inline">{analysis.diameter_measurement?.reference_vessel_diameter_mm == null ? "Unable to calculate" : `${analysis.diameter_measurement.reference_vessel_diameter_mm} mm`}</dd></div>
                <div><dt className="inline font-medium">Minimum lumen diameter: </dt><dd className="inline">{analysis.diameter_measurement?.minimum_lumen_diameter_mm == null ? "Unable to calculate" : `${analysis.diameter_measurement.minimum_lumen_diameter_mm} mm`}</dd></div>
                <div><dt className="inline font-medium">Reference diameter (pixel estimate): </dt><dd className="inline">{analysis.diameter_measurement?.reference_vessel_diameter_px == null ? "Unable to calculate" : `${analysis.diameter_measurement.reference_vessel_diameter_px} px`}</dd></div>
                <div><dt className="inline font-medium">Minimum lumen diameter (pixel estimate): </dt><dd className="inline">{analysis.diameter_measurement?.minimum_lumen_diameter_px == null ? "Unable to calculate" : `${analysis.diameter_measurement.minimum_lumen_diameter_px} px`}</dd></div>
                <div><dt className="inline font-medium">Narrowing percentage: </dt><dd className="inline">{analysis.diameter_measurement?.stenosis_percentage == null ? "Unable to calculate" : `${analysis.diameter_measurement.stenosis_percentage}%`}</dd></div>
                <div><dt className="inline font-medium">Measurement location: </dt><dd className="inline">{analysis.diameter_measurement?.measurement_location || "Unable to calculate"}</dd></div>
                <div><dt className="inline font-medium">Geometry quality: </dt><dd className="inline">{analysis.diameter_measurement?.quality || "unavailable"}</dd></div>
              </dl>
              <p className="mt-2 text-xs">{analysis.diameter_measurement?.reason || "No validated lumen measurements or image calibration are available."} No clinical severity grade is assigned.</p>
            </section>
            <section aria-label="Image calibration metadata" className="mt-3 rounded border bg-slate-50 p-3 text-sm">
              <h4 className="font-medium">Image calibration metadata</h4>
              {analysis.image_calibration?.row_spacing_mm_per_pixel != null && analysis.image_calibration?.column_spacing_mm_per_pixel != null ? (
                <p className="mt-1">DICOM reports row/column PixelSpacing: {analysis.image_calibration.row_spacing_mm_per_pixel} / {analysis.image_calibration.column_spacing_mm_per_pixel} mm per pixel.</p>
              ) : <p className="mt-1">Physical pixel spacing unavailable.</p>}
              {analysis.image_calibration?.calibration_type ? <p>Calibration type: {analysis.image_calibration.calibration_type}</p> : null}
              <p className="mt-1 text-xs">{analysis.image_calibration?.reason || "No verified physical calibration is available."} Calibration verified: {analysis.image_calibration?.calibration_verified ? "yes" : "no"}; image transform verified: {analysis.image_calibration?.transform_verified ? "yes" : "no"}. Reported spacing is retained as metadata only and is not used to calculate lumen diameter or stenosis.</p>
            </section>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[["Binary mask", "mask"], ["Overlay", "overlay"], ["Candidate boxes", "boxes"], ["Probability heatmap", "heatmap"], ["Lumen boundary overlay (validated mask only)", "lumen_overlay"], ["Lumen minimum/reference calipers", "lumen_calipers"], ["Integrated Gradients attribution", "integrated_gradients"], ["Ground-truth / prediction comparison", "ground_truth_comparison"], ["Centerline", "centerline"], ["Perpendicular width sections", "cross_sections"]].map(([label, key]) => artifactUrls[analysis.id]?.[key] ? (
                <figure key={key}><img className="w-full rounded border bg-slate-100" src={artifactUrls[analysis.id][key]} alt={`${label} from model output`} /><figcaption className="mt-1 text-xs text-slate-500">{label}</figcaption></figure>
              ) : null)}
            </div>
            {analysis.candidates?.length ? <ul className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">{analysis.candidates.map((candidate) => <li key={candidate.id} className="rounded border p-2">Candidate {candidate.id}: box {candidate.x}, {candidate.y}, {candidate.width}×{candidate.height}; {candidate.pixel_area} pixels; mean predicted probability {(candidate.mean_predicted_probability ?? candidate.confidence)?.toFixed(3) ?? "unavailable"}</li>)}</ul> : null}
            <p className="mt-3 text-xs text-amber-800">Overlay and probability heatmap visualize segmentation scores; they are not Grad-CAM. Predictions require expert review.</p>
          </article>
        ))}
      </section>
    </div>
  );
}
