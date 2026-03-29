import fs from "node:fs/promises";
import path from "node:path";

/** Ordnernamen, die rekursiv übersprungen werden (Tooling / VCS). */
const SKIP_DIR_NAMES = new Set([
  ".git",
  ".svn",
  ".hg",
  "node_modules",
  ".venv",
  "venv",
  "__pycache__",
  ".idea",
  ".vs"
]);

/**
 * Sammelt alle regulären Dateien unter rootDir (rekursiv).
 */
export async function collectFilesRecursive(rootDir: string): Promise<string[]> {
  const absoluteRoot = path.resolve(rootDir);
  const results: string[] = [];

  async function walk(currentDir: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(currentDir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        if (SKIP_DIR_NAMES.has(entry.name)) {
          continue;
        }
        await walk(fullPath);
      } else if (entry.isFile()) {
        results.push(fullPath);
      }
    }
  }

  await walk(absoluteRoot);
  return results;
}
