import fs from "node:fs/promises";
import type { AppSettings } from "@rag/shared";

export const defaultSettings: AppSettings = {
  activePostgresEnvironmentId: "default",
  postgresEnvironments: [
    {
      id: "default",
      name: "Standard",
      vectorBackend: "postgres",
      dbHost: "localhost",
      dbPort: 5432,
      dbName: "rag",
      dbUser: "postgres",
      dbPassword: "",
      dbSchema: "public",
      dbTableName: "rag_documents",
      sqliteFilePath: "",
      qdrantLocalPath: ""
    }
  ],
  chunkSize: 900,
  chunkOverlap: 15,
  embeddingModel: "paraphrase-multilingual-MiniLM-L12-v2",
  storeMarkdown: true
};

export class SettingsStore {
  public constructor(private readonly settingsPath: string) {}

  public async load(): Promise<AppSettings> {
    try {
      const raw = await fs.readFile(this.settingsPath, "utf-8");
      const parsed = JSON.parse(raw) as Partial<AppSettings>;
      return {
        ...defaultSettings,
        ...parsed
      };
    } catch {
      await this.save(defaultSettings);
      return defaultSettings;
    }
  }

  public async save(settings: AppSettings): Promise<AppSettings> {
    await fs.writeFile(this.settingsPath, JSON.stringify(settings, null, 2), "utf-8");
    return settings;
  }
}
