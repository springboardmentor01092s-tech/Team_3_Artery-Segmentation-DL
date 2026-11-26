import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import Notice from "../components/Notice";
import { apiError } from "../utils/errors";

const empty = {
  case_identifier: "",
  patient_identifier: "",
  age: "",
  gender: "",
  medical_history: "",
  risk_factors: "",
  clinical_notes: "",
  imaging_modality: "CTA",
  scan_date: "",
  anatomical_region: "coronary",
};

export default function CreateCasePage() {
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        ...form,
        age: form.age === "" ? null : Number(form.age),
        scan_date: form.scan_date || null,
      };
      const { data } = await api.post("/api/cases", payload);
      navigate(`/cases/${data.id}`);
    } catch (err) {
      setError(apiError(err, "Could not create case."));
    } finally {
      setBusy(false);
    }
  };

  const field = (key, label, props = {}) => (
    <label className="block text-sm">
      {label}
      <input
        className="mt-1 w-full rounded-lg border px-3 py-2"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        {...props}
      />
    </label>
  );

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4 rounded-xl border bg-white p-6">
      <h2 className="text-2xl font-semibold">Create case</h2>
      <Notice>Use synthetic identifiers only. Do not enter real patient-identifiable information.</Notice>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {field("case_identifier", "Case ID", { required: true, pattern: "[A-Za-z0-9_-]+" })}
        {field("patient_identifier", "Pseudonymous patient ID", { required: true })}
        {field("age", "Age", { type: "number", min: 0, max: 120 })}
        {field("gender", "Gender")}
        {field("imaging_modality", "Imaging modality", { required: true })}
        {field("scan_date", "Scan date", { type: "date" })}
        {field("anatomical_region", "Anatomical region")}
      </div>
      <label className="block text-sm">
        Medical history
        <textarea className="mt-1 w-full rounded-lg border px-3 py-2" value={form.medical_history} onChange={(e) => setForm({ ...form, medical_history: e.target.value })} />
      </label>
      <label className="block text-sm">
        Risk factors
        <textarea className="mt-1 w-full rounded-lg border px-3 py-2" value={form.risk_factors} onChange={(e) => setForm({ ...form, risk_factors: e.target.value })} />
      </label>
      <label className="block text-sm">
        Clinical notes
        <textarea className="mt-1 w-full rounded-lg border px-3 py-2" value={form.clinical_notes} onChange={(e) => setForm({ ...form, clinical_notes: e.target.value })} />
      </label>
      <button disabled={busy} className="rounded-lg bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60">{busy ? "Saving case…" : "Save case"}</button>
    </form>
  );
}
