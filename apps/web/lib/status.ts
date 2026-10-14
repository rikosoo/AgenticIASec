export type ApiStatus = "ok" | "indisponivel";

export function parseHealth(body: unknown): ApiStatus {
  return typeof body === "object" && body !== null && (body as { status?: string }).status === "ok"
    ? "ok"
    : "indisponivel";
}
