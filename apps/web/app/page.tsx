import { parseHealth } from "../lib/status";

export const dynamic = "force-dynamic";

async function apiStatus() {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  try {
    const r = await fetch(`${base}/health`, { cache: "no-store" });
    return parseHealth(await r.json());
  } catch {
    return "indisponivel" as const;
  }
}

export default async function Home() {
  const status = await apiStatus();
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">PromptShield</h1>
      <p className="mt-2 text-slate-600">Console em construção (Etapa 1: esqueleto).</p>
      <p className="mt-6">
        API: <strong>{status === "ok" ? "online" : "indisponível"}</strong>
      </p>
    </main>
  );
}
