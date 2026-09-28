import fs from "node:fs/promises";
import path from "node:path";
import { app } from "electron";

export interface ConnectionConfig {
  apiBaseUrl: string;
  apiKey: string;
}

const FILE_NAME = "connection.json";

function configPath(): string {
  return path.join(app.getPath("userData"), FILE_NAME);
}

export async function loadConnectionConfig(): Promise<ConnectionConfig | null> {
  try {
    const raw = await fs.readFile(configPath(), "utf-8");
    const parsed = JSON.parse(raw) as Partial<ConnectionConfig>;
    const apiBaseUrl = String(parsed.apiBaseUrl ?? "").trim();
    const apiKey = String(parsed.apiKey ?? "").trim();
    if (!apiBaseUrl || !apiKey) {
      return null;
    }
    return { apiBaseUrl, apiKey };
  } catch {
    return null;
  }
}

export async function saveConnectionConfig(config: ConnectionConfig): Promise<ConnectionConfig> {
  const normalized: ConnectionConfig = {
    apiBaseUrl: config.apiBaseUrl.trim().replace(/\/$/, ""),
    apiKey: config.apiKey.trim()
  };
  await fs.mkdir(path.dirname(configPath()), { recursive: true });
  await fs.writeFile(configPath(), JSON.stringify(normalized, null, 2), "utf-8");
  return normalized;
}
