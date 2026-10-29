import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useApi } from "@/lib/api";

const MeCtx = createContext(null);

export function MeProvider({ children }) {
  const api = useApi();
  const [me, setMe] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/me");
      setMe(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "error");
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  return <MeCtx.Provider value={{ me, error, reload: load }}>{children}</MeCtx.Provider>;
}

export const useMe = () => useContext(MeCtx);

export function useLookups() {
  const api = useApi();
  const { me } = useMe();
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const reload = useCallback(async () => {
    const [e, d] = await Promise.all([api.get("/employees"), api.get("/departments")]);
    setEmployees(e.data);
    setDepartments(d.data);
  }, [api]);
  useEffect(() => {
    reload().catch(() => {});
  }, [reload, me?.id]);
  return { employees, departments, reload };
}
