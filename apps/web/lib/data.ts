import "server-only";
import { gunzip } from "node:zlib";
import { readFile } from "node:fs/promises";
import { promisify } from "node:util";
import path from "node:path";
import { cache } from "react";
import type { EnsembleVote, Forecast, Market, MarketRow, Observation, Run, ScanError, Signal, Snapshot, Token, TraderResearch } from "@/types/database";

type LocalData = {
  markets: Market[];
  tokens: Token[];
  snapshots: Snapshot[];
  runs: Run[];
  errors: ScanError[];
  forecasts?: Forecast[];
  ensemble_votes?: EnsembleVote[];
  observations?: Observation[];
  signals?: Signal[];
  trader_research?: TraderResearch[];
};

const dataFile = process.env.POLYEDGE_DATA_FILE || path.resolve(process.cwd(), "../../data/polyedge.json");
const empty: LocalData = { markets: [], tokens: [], snapshots: [], runs: [], errors: [] };
const decompress = promisify(gunzip);

type AppwriteConfig = {
  endpoint: string;
  projectId: string;
  apiKey: string;
  databaseId: string;
  tableId: string;
  bucketId: string;
};

function getAppwriteConfig(): AppwriteConfig | null {
  const endpoint = process.env.APPWRITE_ENDPOINT;
  const projectId = process.env.APPWRITE_PROJECT_ID;
  const apiKey = process.env.APPWRITE_API_KEY;
  if (!endpoint || !projectId || !apiKey) return null;
  return {
    endpoint: endpoint.replace(/\/$/, ""),
    projectId,
    apiKey,
    databaseId: process.env.APPWRITE_DATABASE_ID || "polyedge",
    tableId: process.env.APPWRITE_STATE_TABLE_ID || "state_pointers",
    bucketId: process.env.APPWRITE_STATE_BUCKET_ID || "polyedge-state",
  };
}

function appwriteHeaders(config: AppwriteConfig): HeadersInit {
  return {
    "X-Appwrite-Project": config.projectId,
    "X-Appwrite-Key": config.apiKey,
  };
}

async function readAppwriteState(config: AppwriteConfig): Promise<LocalData> {
  const pointerResponse = await fetch(
    `${config.endpoint}/tablesdb/${config.databaseId}/tables/${config.tableId}/rows/latest`,
    { headers: appwriteHeaders(config), cache: "no-store" },
  );
  if (pointerResponse.status === 404) return empty;
  if (!pointerResponse.ok) throw new Error(`Appwrite state pointer failed (${pointerResponse.status}).`);
  const pointer = await pointerResponse.json() as { file_id: string };
  const fileResponse = await fetch(
    `${config.endpoint}/storage/buckets/${config.bucketId}/files/${pointer.file_id}/download`,
    { headers: appwriteHeaders(config), cache: "no-store" },
  );
  if (!fileResponse.ok) throw new Error(`Appwrite state file failed (${fileResponse.status}).`);
  return JSON.parse((await decompress(Buffer.from(await fileResponse.arrayBuffer()))).toString("utf8")) as LocalData;
}

const load = cache(async (): Promise<LocalData> => {
  const appwrite = getAppwriteConfig();
  if (appwrite) return readAppwriteState(appwrite);
  try {
    return JSON.parse(await readFile(dataFile, "utf8")) as LocalData;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return empty;
    throw error;
  }
});

export async function hasLocalData(): Promise<boolean> {
  return (await load()).runs.length > 0;
}

export async function count(table: string, filter?: Record<string, string>): Promise<number> {
  if (table !== "markets") throw new Error(`Unsupported local collection: ${table}`);
  const markets = (await load()).markets;
  if (!filter) return markets.length;
  return markets.filter((market) =>
    Object.entries(filter).every(([key, value]) =>
      String(market[key as keyof Market]) === value.replace(/^eq\./, ""),
    ),
  ).length;
}

export async function getMarkets(): Promise<MarketRow[]> {
  const { markets, tokens, snapshots } = await load();
  const latest = new Map<string, Snapshot>();
  for (const snapshot of snapshots) {
    const current = latest.get(snapshot.token_id);
    if (!current || current.captured_at < snapshot.captured_at) latest.set(snapshot.token_id, snapshot);
  }
  const tokenMap = new Map<string, MarketRow["market_tokens"]>();
  for (const token of tokens) {
    const group = tokenMap.get(token.market_id) ?? [];
    group.push({ ...token, market_snapshots: latest.has(token.token_id) ? [latest.get(token.token_id)!] : [] });
    tokenMap.set(token.market_id, group);
  }
  return [...markets]
    .map((market) => ({
      ...market,
      // List views do not display raw API payloads or long descriptions.
      raw_metadata: {},
      description: null,
      resolution_rules: null,
      market_tokens: tokenMap.get(market.id) ?? [],
    }))
    .sort((a, b) => {
      const aHasBook = a.market_tokens.some((token) => token.market_snapshots.length > 0);
      const bHasBook = b.market_tokens.some((token) => token.market_snapshots.length > 0);
      return Number(bHasBook) - Number(aHasBook) || b.updated_at.localeCompare(a.updated_at);
    })
    .slice(0, 500);
}

export async function getMarket(id: string): Promise<Market | null> {
  return (await load()).markets.find((market) => market.id === id) ?? null;
}

export async function getTokens(id: string): Promise<Token[]> {
  return (await load()).tokens.filter((token) => token.market_id === id);
}

export async function getSnapshots(id: string): Promise<Snapshot[]> {
  return (await load()).snapshots
    .filter((snapshot) => snapshot.market_id === id)
    .sort((a, b) => b.captured_at.localeCompare(a.captured_at))
    .slice(0, 200);
}

export async function getRuns(): Promise<Run[]> {
  return [...(await load()).runs].sort((a, b) => b.started_at.localeCompare(a.started_at)).slice(0, 100);
}

export async function getErrors(): Promise<ScanError[]> {
  return [...(await load()).errors].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 100);
}

export async function getLatestSnapshotAt(): Promise<string | null> {
  return (await load()).snapshots.reduce<string | null>(
    (latest, snapshot) => !latest || snapshot.captured_at > latest ? snapshot.captured_at : latest,
    null,
  );
}

export async function getLatestForecasts(): Promise<Forecast[]> {
  const latest = new Map<string, Forecast>();
  for (const forecast of (await load()).forecasts ?? []) {
    const key = `${forecast.city}|${forecast.target_date}`;
    const current = latest.get(key);
    if (!current || current.collected_at < forecast.collected_at) latest.set(key, forecast);
  }
  return [...latest.values()].sort((a, b) =>
    a.target_date.localeCompare(b.target_date) || a.city.localeCompare(b.city),
  );
}

export async function getEnsembleVotes(): Promise<EnsembleVote[]> {
  return (await load()).ensemble_votes ?? [];
}

export async function getObservations(): Promise<Observation[]> {
  return (await load()).observations ?? [];
}

export async function getSignals(): Promise<Signal[]> {
  return (await load()).signals ?? [];
}

export async function getTraderResearch(): Promise<TraderResearch[]> {
  return (await load()).trader_research ?? [];
}

export async function health(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    return res.status < 500;
  } catch {
    return false;
  }
}
