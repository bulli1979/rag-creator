import path from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow } from "electron";
import { registerIpcHandlers } from "./ipc.js";
import { ChatApiClient } from "./services/chatApiClient.js";
import { loadConnectionConfig } from "./services/connectionConfigStore.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isDevelopment = process.env.NODE_ENV !== "production";

const openDevToolsInDev =
  isDevelopment &&
  process.env.RAG_OPEN_DEVTOOLS !== "0" &&
  process.env.RAG_OPEN_DEVTOOLS?.toLowerCase() !== "false";

const PRELOAD_PATH = path.join(__dirname, "preload.cjs");
let mainWindow: BrowserWindow | null = null;
let apiClient: ChatApiClient;

async function createMainWindow(): Promise<void> {
  const stored = await loadConnectionConfig();
  apiClient = new ChatApiClient(
    stored?.apiBaseUrl || process.env.RAG_API_URL || "http://localhost:8000",
    stored?.apiKey || process.env.RAG_API_KEY || ""
  );

  const workspaceRoot = path.resolve(__dirname, "../../..");
  const appIconPath = path.join(workspaceRoot, "assets", "rag-ingest-studio-icon.png");

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 760,
    icon: appIconPath,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      sandbox: false
    }
  });

  registerIpcHandlers(() => apiClient);

  if (isDevelopment) {
    await mainWindow.loadURL("http://localhost:5174");
    if (openDevToolsInDev) {
      mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  } else {
    await mainWindow.loadFile(path.resolve(__dirname, "../../../apps/renderer/dist/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  await createMainWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
