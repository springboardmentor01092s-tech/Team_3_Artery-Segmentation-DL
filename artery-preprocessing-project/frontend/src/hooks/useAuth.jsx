import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const persist = (accessToken, profile) => {
    localStorage.setItem("artery_auth", JSON.stringify({ accessToken, user: profile }));
    setUser(profile);
  };

  const load = async () => {
    const raw = localStorage.getItem("artery_auth");
    if (!raw) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get("/api/auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("artery_auth");
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      hasRole: (...roles) => Boolean(user && roles.includes(user.role)),
      hasPermission: (permission) => Boolean(user?.permissions?.includes(permission)),
      login: async (email, password) => {
        const { data } = await api.post("/api/auth/login", { email, password });
        localStorage.setItem("artery_auth", JSON.stringify({ accessToken: data.access_token }));
        const me = await api.get("/api/auth/me");
        persist(data.access_token, me.data);
        return me.data;
      },
      register: async (payload) => {
        await api.post("/api/auth/register", payload);
        return true;
      },
      logout: async () => {
        try {
          await api.post("/api/auth/logout");
        } catch {
          /* token may already be invalid */
        }
        localStorage.removeItem("artery_auth");
        setUser(null);
      },
      refresh: load,
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
