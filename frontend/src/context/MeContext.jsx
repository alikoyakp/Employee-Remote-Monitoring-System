import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const MeCtx = createContext(null);

export function MeProvider({ children }) {
  // me: null = checking, false = signed out, object = signed in
  const [me, setMe] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/me");
      setMe(r.data);
      setError(null);
    } catch (e) {
      if (e?.response?.status === 401) setMe(false);
      else setError(e?.response?.data?.detail || e.message || "error");
    }
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    setMe(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return <MeCtx.Provider value={{ me, error, reload: load, logout }}>{children}</MeCtx.Provider>;
}

export const useMe = () => useContext(MeCtx);

export function useLookups() {
  const { me } = useMe();
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const reload = useCallback(async () => {
    const [e, d] = await Promise.all([api.get("/employees"), api.get("/departments")]);
    setEmployees(e.data);
    setDepartments(d.data);
  }, []);
  useEffect(() => {
    reload().catch(() => {});
  }, [reload, me?.id]);
  return { employees, departments, reload };
}
