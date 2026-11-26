import { useEffect, useState } from "react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

const roles = ["administrator", "radiologist", "researcher", "data_scientist"];

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyUsers, setBusyUsers] = useState(() => new Set());

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/admin/users");
      setUsers(data);
      setError("");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const update = async (user, patch) => {
    setBusyUsers((current) => new Set(current).add(user.id));
    setError("");
    try {
      await api.patch(`/api/admin/users/${user.id}`, patch);
      await load();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusyUsers((current) => {
        const next = new Set(current);
        next.delete(user.id);
        return next;
      });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">User management</h2>
        <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-60" disabled={loading} onClick={load}>
          {loading ? "Loading users..." : "Reload users"}
        </button>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {loading ? <Spinner label="Loading users..." /> : null}
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Active</th>
            </tr>
          </thead>
          <tbody>
            {!loading && users.length === 0 ? <tr><td className="px-4 py-3 text-slate-500" colSpan={4}>No user accounts found.</td></tr> : null}
            {users.map((user) => (
              <tr key={user.id} className="border-t">
                <td className="px-4 py-3">{user.full_name}</td>
                <td className="px-4 py-3">{user.email}</td>
                <td className="px-4 py-3">
                  <select className="rounded border px-2 py-1" value={user.role} disabled={busyUsers.has(user.id)} onChange={(e) => update(user, { role: e.target.value })}>
                    {roles.map((role) => (
                      <option key={role}>{role}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button className="rounded border px-2 py-1 disabled:opacity-60" disabled={busyUsers.has(user.id)} onClick={() => update(user, { is_active: !user.is_active })}>
                    {busyUsers.has(user.id) ? "Saving..." : user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
