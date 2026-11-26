import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Notice from "../components/Notice";
import { useAuth } from "../hooks/useAuth";
import { apiError } from "../utils/errors";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(form);
      navigate("/login");
    } catch (err) {
      setError(apiError(err, "Registration failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold">Create an account</h1>
        <Notice>
          Public registration uses the researcher role. Administrator accounts must be created locally with the bootstrap
          script.
        </Notice>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <label className="block text-sm">
          Full name
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            required
            minLength={2}
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </label>
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
          Password (min 8 characters)
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        <button disabled={busy} className="w-full rounded-lg bg-teal-700 py-2 text-white">
          {busy ? "Creating..." : "Register"}
        </button>
        <p className="text-sm text-slate-600">
          Already registered? <Link className="text-teal-700" to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
