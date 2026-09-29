import axios from "axios";

export const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const api = axios.create({ baseURL: `${API_URL}/api` });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem("access") && !err.config.url.includes("auth/login")) {
      localStorage.removeItem("access");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function errorText(err) {
  const d = err?.response?.data;
  if (!d) return err?.message || "Something went wrong";
  if (typeof d === "string") return d.slice(0, 200);
  if (d.detail) return d.detail;
  if (d.error) return d.error;
  return Object.entries(d)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
    .join(" | ");
}

export default api;
