import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });
let refreshing = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config || {};
    const url = cfg.url || "";
    if (error.response?.status === 401 && !cfg._retried && !url.startsWith("/auth/")) {
      cfg._retried = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh").finally(() => { refreshing = null; });
        await refreshing;
        return api(cfg);
      } catch {}
    }
    return Promise.reject(error);
  },
);

export const useApi = () => api;
export default api;

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(", ");
  if (d && typeof d.msg === "string") return d.msg;
  return e?.message || "Something went wrong";
}

export async function blobError(e) {
  const data = e?.response?.data;
  if (data instanceof Blob) {
    try { return JSON.parse(await data.text()).detail || "Download failed"; } catch { return "Download failed"; }
  }
  return errMsg(e);
}

export async function downloadFile(client, url, params, filename) {
  const r = await client.get(url, { params, responseType: "blob" });
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 2000);
}

export const fmtMin = (m) => {
  const v = Math.max(0, Math.round(m || 0));
  return `${Math.floor(v / 60)}h ${String(v % 60).padStart(2, "0")}m`;
};
export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—");
export const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—");
export const isoDay = (d = new Date()) => d.toISOString().slice(0, 10);
export const daysAgo = (n) => isoDay(new Date(Date.now() - n * 86400000));
export const sinceText = (iso) => {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
};
