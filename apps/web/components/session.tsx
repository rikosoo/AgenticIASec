"use client";
import { createContext, useContext, type ReactNode } from "react";
import { api, useLoad } from "@/lib/api";
import type { Me, Tenant } from "@/lib/types";
import { ErrorBox, Loading } from "./ui";

interface Ctx { me: Me; tenant: Tenant }
const SessionCtx = createContext<Ctx | null>(null);

export const useSession = () => {
  const v = useContext(SessionCtx);
  if (!v) throw new Error("fora do SessionProvider");
  return v;
};

export const canTriage = (role: Me["role"]) => role === "admin" || role === "analista";

export function SessionProvider({ children }: { children: (ctx: Ctx) => ReactNode }) {
  const { data, error, loading, reload } = useLoad(async () => {
    const [me, tenant] = await Promise.all([api<Me>("v1/me"), api<Tenant>("v1/tenant")]);
    return { me, tenant };
  }, []);
  if (loading) return <div className="p-6"><Loading label="Abrindo sessão…" /></div>;
  if (error || !data) return <div className="p-6"><ErrorBox message={error ?? "Sem sessão"} onRetry={reload} /></div>;
  return <SessionCtx.Provider value={data}>{children(data)}</SessionCtx.Provider>;
}
