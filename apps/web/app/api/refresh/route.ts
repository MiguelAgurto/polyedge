import { spawn } from "node:child_process";
import path from "node:path";

export const runtime = "nodejs";

function appwriteConfig() {
  const endpoint = process.env.APPWRITE_ENDPOINT;
  const projectId = process.env.APPWRITE_PROJECT_ID;
  const apiKey = process.env.APPWRITE_API_KEY;
  const functionId = process.env.APPWRITE_SCANNER_FUNCTION_ID || "polyedge-scanner";
  if (!endpoint || !projectId || !apiKey) return null;
  return { endpoint: endpoint.replace(/\/$/, ""), projectId, apiKey, functionId };
}

async function startAppwriteRefresh(config: NonNullable<ReturnType<typeof appwriteConfig>>) {
  const response = await fetch(`${config.endpoint}/functions/${config.functionId}/executions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Appwrite-Project": config.projectId,
      "X-Appwrite-Key": config.apiKey,
    },
    body: JSON.stringify({
      async: true,
      body: JSON.stringify({ source: "dashboard" }),
      method: "POST",
      path: "/",
    }),
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Could not start the Appwrite refresh (${response.status}): ${detail.slice(0, 300)}`);
  }
  const execution = await response.json() as { $id: string; status: string };
  return Response.json({ queued: true, execution_id: execution.$id, status: execution.status });
}

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ error: "Refresh requests must come from this dashboard." }, { status: 403 });
  }
  const remote = appwriteConfig();
  if (remote) {
    try {
      return await startAppwriteRefresh(remote);
    } catch (error) {
      return Response.json({ error: error instanceof Error ? error.message : "Could not start the Appwrite refresh." }, { status: 503 });
    }
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
