import { spawn } from "node:child_process";
import path from "node:path";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ error: "Refresh requests must come from this dashboard." }, { status: 403 });
  }
  const root = path.resolve(process.cwd(), "../..");
  const python = process.env.POLYEDGE_PYTHON || path.join(root, "services/scanner/.venv/bin/python");
  const result = await new Promise<{ code: number; output: string; error: string }>((resolve) => {
    const child = spawn(python, ["-m", "polyedge.jobs.refresh_now"], {
      cwd: root,
      env: { ...process.env, POLYEDGE_STORAGE: "local" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    let error = "";
    child.stdout.on("data", (chunk: Buffer) => { output = (output + chunk.toString()).slice(-20000); });
    child.stderr.on("data", (chunk: Buffer) => { error = (error + chunk.toString()).slice(-20000); });
    child.on("error", (cause) => resolve({ code: 1, output, error: cause.message }));
    child.on("close", (code) => resolve({ code: code ?? 1, output, error }));
  });
  const lastLine = result.output.trim().split("\n").at(-1);
  if (result.code !== 0) {
    const lastError = result.error.trim().split("\n").at(-1) || "The local refresh failed.";
    let detail = lastError;
    try { detail = JSON.parse(lastError).error || lastError; } catch { /* Use plain error text. */ }
    return Response.json({ error: detail }, { status: 503 });
  }
  try {
    return Response.json(JSON.parse(lastLine || "{}"));
  } catch {
    return Response.json({ error: "The refresh completed without a readable result." }, { status: 500 });
  }
}
