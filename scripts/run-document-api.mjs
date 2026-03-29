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

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
  { cwd: apiDir, stdio: "inherit", shell: false }
);

child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code ?? 0);
});
