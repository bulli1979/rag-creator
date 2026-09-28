/**
 * Startet uvicorn fuer documentApi mit dem lokalen .venv-Python (Windows/macOS/Linux).
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.join(__dirname, "..");
const apiDir = path.join(repoRoot, "documentApi");
const win = process.platform === "win32";
const python = path.join(apiDir, win ? ".venv/Scripts/python.exe" : ".venv/bin/python");

if (!fs.existsSync(python)) {
  console.error(
    "[documentApi] Python venv nicht gefunden:\n",
    python,
    "\nBitte in documentApi ausfuehren: python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt (Windows)"
  );
  process.exit(1);
}

// Qdrant embedded: exklusive Sperre auf dem Ordner — mit uvicorn --reload kann der Reloader/Worker kurz ueberlappen
// und die API startet nicht. Standard: ohne Reload; bei Bedarf: DOCUMENT_API_RELOAD=1
// DOCUMENT_API_HOST: z. B. 0.0.0.0 fuer Zugriff im LAN (Clients dann RAG_API_URL auf Host-IP setzen)
const host = process.env.DOCUMENT_API_HOST?.trim() || "127.0.0.1";
const argv = ["-m", "uvicorn", "app.main:app", "--host", host, "--port", "8000"];
const reload =
  process.env.DOCUMENT_API_RELOAD === "1" || process.env.DOCUMENT_API_RELOAD === "true";
if (reload) {
  argv.push("--reload");
}

const child = spawn(python, argv, { cwd: apiDir, stdio: "inherit", shell: false });

child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code ?? 0);
});
