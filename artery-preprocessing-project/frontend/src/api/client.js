import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

api.interceptors.request.use((config) => {
  const raw = localStorage.getItem("artery_auth");
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed.accessToken) {
        config.headers.Authorization = `Bearer ${parsed.accessToken}`;
      }
    } catch {
      // A damaged browser session must not prevent the request from reaching
      // public endpoints or the login flow.
      localStorage.removeItem("artery_auth");
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    if (status === 401 && !window.location.pathname.startsWith("/login")) {
      localStorage.removeItem("artery_auth");
      if (typeof detail === "string" && detail.toLowerCase().includes("expired")) {
        window.location.assign("/login?reason=expired");
      }
    }
    return Promise.reject(error);
  }
);

export default api;
