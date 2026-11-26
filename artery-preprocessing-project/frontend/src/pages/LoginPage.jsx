import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Notice from "../components/Notice";
import { useAuth } from "../hooks/useAuth";
import { apiError } from "../utils/errors";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(params.get("reason") === "expired" ? "Your session expired. Please log in again." : "");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(form.email, form.password);
      navigate("/dashboard");
    } catch (err) {
      setError(apiError(err, "Login failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-8 shadow-sm">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-teal-700">Artery preprocessing</p>
          <h1 className="mt-2 text-2xl font-semibold">Sign in</h1>
        </div>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <label className="block text-sm">
          Email
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            type="password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        <button disabled={busy} className="w-full rounded-lg bg-teal-700 py-2 text-white disabled:opacity-60">
          {busy ? "Signing in..." : "Sign in"}
        </button>
        <p className="text-sm text-slate-600">
          Need an account? <Link className="text-teal-700" to="/register">Register</Link>
        </p>
      </form>
    </div>
  );
}
