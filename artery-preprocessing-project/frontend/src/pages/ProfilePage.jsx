import { useState } from "react";
import api from "../api/client";
import Notice from "../components/Notice";
import { useAuth } from "../hooks/useAuth";
import { apiError } from "../utils/errors";

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(""); setMessage("");
    try {
      const payload = { full_name: fullName };
      if (password) payload.password = password;
      await api.patch("/api/auth/me", payload);
      setPassword("");
      setMessage("Profile updated.");
      await refresh();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="max-w-lg space-y-4 rounded-xl border bg-white p-6">
      <h2 className="text-2xl font-semibold">Profile</h2>
      {message ? <Notice tone="success">{message}</Notice> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      <p className="text-sm text-slate-500">Email: {user?.email}</p>
      <p className="text-sm text-slate-500">Role: {user?.role}</p>
      <label className="block text-sm">
        Full name
        <input className="mt-1 w-full rounded-lg border px-3 py-2" value={fullName} onChange={(e) => setFullName(e.target.value)} minLength={2} maxLength={80} required disabled={busy} />
      </label>
      <label className="block text-sm">
        New password (optional)
        <input className="mt-1 w-full rounded-lg border px-3 py-2" type="password" minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
      </label>
      <button disabled={busy} className="rounded-lg bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60">{busy ? "Saving…" : "Save profile"}</button>
    </form>
  );
}
