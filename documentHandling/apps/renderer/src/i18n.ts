import { useState, useCallback, useMemo } from "react";

export type Locale = "de" | "en";

const translations = {
  de: {
    "app.title": "RAG Ingest Studio",
    "tabs.documents": "Dokumente",
    "tabs.models": "Modelle",
    "tabs.settings": "Einstellungen",
    "header.addDocuments": "Dokumente hinzufügen",
    "header.addFolder": "Ordner hinzufügen",
    "header.startFolderIngest": "Ordner einlesen",
    "header.folderIngestNeedPick": "Zuerst „Ordner hinzufügen“ und einen Ordner wählen.",
    "header.clearFolderPick": "Auswahl aufheben",
    "header.folderIngestRunning": "Einlesen…",
    "header.reindexSelected": "Ausgewählte neu indexieren",
    "header.reindexAll": "Alle neu indexieren",
    "header.reindexAllConfirm":
      "Alle {0} Dokumente neu indexieren? Das kann je nach Anzahl und Größe lange dauern und die Datenbank belasten.",
    "header.reindexAllNone": "Keine Dokumente in der Liste — nichts zu erneuern.",
    "header.reindexAllStarted": "Neu-Indexierung für {0} Dokumente wurde angestoßen (Fortschritt unter Jobs).",
    "header.reindexAllRunning": "Alle neu indexieren …",
    "header.removeSelected": "Ausgewählte entfernen",
    "header.exportCsv": "CSV exportieren",
    "drop.ready":
      "Dateien hierher ziehen oder im Bereich „Ordner rekursiv einlesen“ darunter Ordner wählen und einlesen.",
    "drop.locked": "Upload gesperrt: Bitte zuerst in den Settings den Connection Test erfolgreich ausführen.",
    "upload.folderSectionTitle": "Ordner rekursiv einlesen",
    "upload.title": "Upload Optionen",
    "upload.tags": "Tags (kommagetrennt)",
    "upload.source": "Quelle / Projekt",
    "upload.embeddingModel": "Embedding-Modell",
    "upload.embeddingModelHint":
      "Auswahl gilt für diesen Upload und wird als App-Default gespeichert (Chat nutzt dasselbe Modell). Nur 384-Dimension-Modelle.",
    "upload.folderHint":
      "„Ordner hinzufügen“ wählt den Ordner, „Ordner einlesen“ startet Upload und Indexierung für alle Dateien inkl. Unterordnern (Parsen, Embeddings, Vektor-DB). Übersprungen: u. a. .git, node_modules, .venv. Tags und Quelle gelten pro Datei.",
    "upload.folderPickReady": "Ordner gewählt — jetzt „Ordner einlesen“ drücken (oder Auswahl aufheben).",
    "upload.folderEmpty": "Keine Dateien im Ordner (oder nur übersprungene Verzeichnisse).",
    "upload.folderQueued":
      "{0} Dateien gefunden, {1} Dokumente hochgeladen — Indexierung läuft automatisch im Hintergrund (Fortschritt unter Jobs).",
    "upload.folderError": "Ordner-Upload fehlgeschlagen.",
    "upload.filePickError": "Dateiauswahl/Upload fehlgeschlagen.",
    "upload.dropError": "Drag-and-Drop-Upload fehlgeschlagen.",
    "upload.noRagApi": "Electron-Bridge ragApi fehlt — läuft die App in einem normalen Browser? Nur mit Electron starten.",
    "upload.pickFolderUnavailable": "ragApi.pickFolder fehlt — im Ordner apps/main „npm run build“ ausführen und App neu starten (preload.cjs).",
    "upload.uploadFolderUnavailable": "ragApi.uploadFolderFromPath fehlt — Main-Prozess/Preload neu bauen.",
    "upload.folderIngestNoFolder": "Kein Ordner gewählt — zuerst „Ordner hinzufügen“ nutzen.",
    "upload.folderPickEmptyPath": "Ordnerdialog lieferte einen leeren Pfad.",
    "upload.actionLogTitle": "Aktionsprotokoll (Ordner & Upload)",
    "upload.actionLogClear": "Log leeren",
    "upload.actionLogEmpty": "Noch keine Einträge — Klicks auf Ordner-Buttons erscheinen hier und in der DevTools-Konsole (F12).",
    "doclist.title": "Dokumentliste",
    "doclist.search": "Suche",
    "doclist.status": "Status",
    "doclist.type": "Typ",
    "doclist.tag": "Tag",
    "doclist.all": "Alle",
    "doclist.file": "Datei",
    "doclist.chunks": "Chunks",
    "doclist.size": "Größe",
    "doclist.tags": "Tags",
    "doclist.source": "Quelle",
    "doclist.lastProcessed": "Letzte Verarbeitung",
    "doclist.actions": "Aktionen",
    "doclist.viewCorpus": "Corpus anzeigen",
    "doclist.reindex": "Neu indexieren",
    "doclist.remove": "Entfernen",
    "models.title": "LLM-Backends & Modelle",
    "models.intro":
      "Wählen Sie das aktive Chat-Modell. Die Liste kommt von Ollama; die Auswahl gilt für alle Clients (Chat, Web, Batch).",
    "models.badgeBuiltin": "Fest integriert",
    "models.ollama.name": "Ollama",
    "models.ollama.description":
      "Standard-Backend für Chat und lokale Modellausführung. Läuft auf dem Server (localhost:11434). Dieser Eintrag kann nicht entfernt werden.",
    "models.ollamaEndpoint": "Abgefragte Ollama-Adresse (aus Chat-Einstellungen llmBaseUrl):",
    "models.activeLabel": "Aktives Chat-Modell",
    "models.activeCurrent": "Aktuell aktiv",
    "models.activeBadge": "Aktiv",
    "models.activeChipLabel": "Modell",
    "models.activeChipUnknown": "unbekannt",
    "models.activeChipHint": "Aktives Chat-Modell — Klick öffnet den Tab Modelle",
    "models.select": "Auswählen",
    "models.activeSaved": "Aktives Modell gespeichert: {0}",
    "models.activeSaveError": "Modell konnte nicht gespeichert werden",
    "models.notInstalled": "nicht in Ollama-Liste",
    "models.colAction": "Aktion",
    "models.refresh": "Liste aktualisieren",
    "models.loading": "Lade …",
    "models.empty": "Keine Modelle gefunden — auf dem Ollama-Host z. B. „ollama pull …“ ausführen.",
    "models.colName": "Modell",
    "models.colSize": "Größe",
    "models.colModified": "Geändert",
    "models.apiUnavailable": "listOllamaModels nicht verfügbar — Electron-Main/Preload neu bauen und App neu starten.",
    "models.ranking.title": "Retrieval-Ranking",
    "models.ranking.intro":
      "Steuert, worauf die Chunk-Auswahl nach der Vektorsuche mehr Gewicht legt. Die Schieberegler sind relativ und werden serverseitig auf 100 % normalisiert.",
    "models.ranking.similarity": "Embedding-Ähnlichkeit (wie beim Chunking)",
    "models.ranking.lexical": "Exakte Wortformen (Lexikal)",
    "models.ranking.numeric": "Zahlen-Übereinstimmung",
    "models.ranking.hint":
      "Tipp bei Zeitform-/Flexionsproblemen: Lexikal niedrig oder auf 0 — Embedding höher. Zahlen beibehalten, wenn exakte Werte wichtig sind.",
    "models.ranking.save": "Ranking speichern",
    "models.ranking.saving": "Speichere …",
    "models.ranking.saved": "Ranking-Gewichte gespeichert.",
    "models.ranking.saveError": "Ranking konnte nicht gespeichert werden",
    "models.ranking.reset": "Standard (90 / 5 / 5)",
    "models.ranking.loading": "Chat-Einstellungen werden geladen …",
    "settings.title": "Einstellungen",
    "settings.activePostgresEnv": "Aktive Umgebung (Ziel für Upload & Index)",
    "settings.vectorBackend": "Vektor-Datenbank",
    "settings.vectorBackend.postgres": "PostgreSQL (pgvector)",
    "settings.vectorBackend.sqlite": "SQLite (embedded, kein Server)",
    "settings.vectorBackend.qdrant": "Qdrant (embedded, lokaler Ordner)",
    "settings.sqliteFilePath": "SQLite-Datei (optional)",
    "settings.sqliteFilePathPlaceholder": "Leer = automatisch unter ~/RAGIngestStudio/vector_sqlite/<Umgebungs-ID>.sqlite",
    "settings.qdrantLocalPath": "Qdrant-Speicherordner (optional)",
    "settings.qdrantLocalPathPlaceholder": "Leer = automatisch unter ~/RAGIngestStudio/vector_qdrant/<Umgebungs-ID>/",
    "settings.envName": "Anzeigename der Umgebung",
    "settings.addPostgresEnv": "Umgebung hinzufügen",
    "settings.removePostgresEnv": "Aktive Umgebung löschen",
    "settings.dbHost": "DB Host",
    "settings.dbPort": "DB Port",
    "settings.dbName": "DB Name",
    "settings.dbSchema": "Postgres-Schema",
    "settings.dbUser": "DB Benutzer",
    "settings.dbPassword": "DB Passwort",
    "settings.vectorTable": "Vektor-Tabellenname",
    "settings.chunkSize": "Chunk-Größe",
    "settings.chunkOverlap": "Chunk-Überlappung (%)",
    "settings.embeddingModel": "Embedding-Modell",
    "settings.embeddingModelHint": "Nur Modelle mit 384 Dimensionen (kompatibel zu Qdrant embedded).",
    "settings.storeMarkdown": "Markdown speichern",
    "settings.save": "Einstellungen speichern",
    "settings.connectionTest": "Connection Test",
    "settings.connectionTestRunning": "Teste …",
    "settings.connectionTestRunningDetail":
      "Verbindung zu Postgres wird geprüft und das Vektor-Schema vorbereitet …",
    "settings.connectionTestUsesForm":
      "Der Test verwendet die Werte in diesem Formular (wie in pgAdmin). Bei Erfolg werden sie gespeichert.",
    "settings.passwordKeepHint":
      "Passwort: neu eintragen und Speichern setzt es fest. Leeres Feld behält das zuletzt gespeicherte Passwort (wird nicht mit leer überschrieben).",
    "settings.connectionTestResponse": "Antwort (Connection Test / Fehler)",
    "settings.loading": "Einstellungen werden geladen...",
    "settings.loadError":
      "API nicht erreichbar (documentApi auf Port 8000?). Es werden lokale Standard-Einstellungen angezeigt — bitte Backend starten und App neu laden.",
    "settings.connectionTestError":
      "Verbindungstest fehlgeschlagen (Netzwerk, Timeout oder Postgres). Bitte Einstellungen prüfen und erneut testen.",
    "settings.saved": "Einstellungen gespeichert. Bitte Connection Test erneut ausführen.",
    "settings.testFirst": "Bitte zuerst Connection Test ausführen.",
    "settings.language": "Sprache",
    "jobs.title": "Job Events",
    "corpus.title": "Corpus Viewer",
    "corpus.saveAndReindex": "Speichern und neu indexieren",
    "corpus.close": "Schließen",
  },
  en: {
    "app.title": "RAG Ingest Studio",
    "tabs.documents": "Documents",
    "tabs.models": "Models",
    "tabs.settings": "Settings",
    "header.addDocuments": "Add Documents",
    "header.addFolder": "Add folder",
    "header.startFolderIngest": "Ingest folder",
    "header.folderIngestNeedPick": "Choose a folder with Add folder first.",
    "header.clearFolderPick": "Clear selection",
    "header.folderIngestRunning": "Ingesting…",
    "header.reindexSelected": "Reindex Selected",
    "header.reindexAll": "Reindex all",
    "header.reindexAllConfirm":
      "Reindex all {0} documents? This may take a long time and load the database depending on count and size.",
    "header.reindexAllNone": "No documents in the list — nothing to refresh.",
    "header.reindexAllStarted": "Reindex queued for {0} documents (see Jobs for progress).",
    "header.reindexAllRunning": "Reindexing all …",
    "header.removeSelected": "Remove Selected",
    "header.exportCsv": "Export CSV",
    "drop.ready":
      "Drag and drop files here, or use the Ingest folder section below to pick a folder and start.",
    "drop.locked": "Upload locked: Please run Connection Test in Settings first.",
    "upload.folderSectionTitle": "Ingest folder (recursive)",
    "upload.title": "Upload Options",
    "upload.tags": "Tags (comma-separated)",
    "upload.source": "Source / Project",
    "upload.embeddingModel": "Embedding model",
    "upload.embeddingModelHint":
      "Applies to this upload and is saved as the app default (chat uses the same model). 384-dimension models only.",
    "upload.folderHint":
      "Add folder picks the directory; Ingest folder starts upload and indexing for all files including subfolders (parse, embeddings, vector store). Skips include .git, node_modules, .venv. Tags and source apply to each file.",
    "upload.folderPickReady": "Folder selected — press Ingest folder (or clear selection).",
    "upload.folderEmpty": "No files in that folder (or only skipped directories).",
    "upload.folderQueued":
      "Found {0} files, uploaded {1} documents — indexing runs automatically in the background (see Jobs below).",
    "upload.folderError": "Folder upload failed.",
    "upload.filePickError": "File picker / upload failed.",
    "upload.dropError": "Drag-and-drop upload failed.",
    "upload.noRagApi": "Electron bridge ragApi is missing — open this app with Electron, not a normal browser.",
    "upload.pickFolderUnavailable": "ragApi.pickFolder is missing — run npm run build in apps/main and restart (preload).",
    "upload.uploadFolderUnavailable": "ragApi.uploadFolderFromPath is missing — rebuild main/preload.",
    "upload.folderIngestNoFolder": "No folder selected — use Add folder first.",
    "upload.folderPickEmptyPath": "Folder dialog returned an empty path.",
    "upload.actionLogTitle": "Action log (folder & upload)",
    "upload.actionLogClear": "Clear log",
    "upload.actionLogEmpty": "No entries yet — folder button clicks show here and in DevTools (F12).",
    "doclist.title": "Document List",
    "doclist.search": "Search",
    "doclist.status": "Status",
    "doclist.type": "Type",
    "doclist.tag": "Tag",
    "doclist.all": "All",
    "doclist.file": "File",
    "doclist.chunks": "Chunks",
    "doclist.size": "Size",
    "doclist.tags": "Tags",
    "doclist.source": "Source",
    "doclist.lastProcessed": "Last Processed",
    "doclist.actions": "Actions",
    "doclist.viewCorpus": "View Corpus",
    "doclist.reindex": "Reindex",
    "doclist.remove": "Remove",
    "models.title": "LLM backends & models",
    "models.intro":
      "Choose the active chat model. The list comes from Ollama; the selection applies to all clients (chat, web, batch).",
    "models.badgeBuiltin": "Built-in",
    "models.ollama.name": "Ollama",
    "models.ollama.description":
      "Default backend for chat and local inference. Runs on the server (localhost:11434). This entry cannot be removed.",
    "models.ollamaEndpoint": "Ollama address used (from chat settings llmBaseUrl):",
    "models.activeLabel": "Active chat model",
    "models.activeCurrent": "Currently active",
    "models.activeBadge": "Active",
    "models.activeChipLabel": "Model",
    "models.activeChipUnknown": "unknown",
    "models.activeChipHint": "Active chat model — click to open Models tab",
    "models.select": "Select",
    "models.activeSaved": "Active model saved: {0}",
    "models.activeSaveError": "Could not save model",
    "models.notInstalled": "not in Ollama list",
    "models.colAction": "Action",
    "models.refresh": "Refresh list",
    "models.loading": "Loading…",
    "models.empty": "No models found — on the Ollama host run e.g. “ollama pull …”.",
    "models.colName": "Model",
    "models.colSize": "Size",
    "models.colModified": "Modified",
    "models.apiUnavailable": "listOllamaModels unavailable — rebuild Electron main/preload and restart.",
    "models.ranking.title": "Retrieval ranking",
    "models.ranking.intro":
      "Controls what the chunk selection emphasizes after vector search. Sliders are relative and normalized to 100% on the server.",
    "models.ranking.similarity": "Embedding similarity (same as chunking)",
    "models.ranking.lexical": "Exact word forms (lexical)",
    "models.ranking.numeric": "Numeric match",
    "models.ranking.hint":
      "Tip for tense/inflection misses: keep lexical low or 0 — raise embedding. Keep numeric if exact values matter.",
    "models.ranking.save": "Save ranking",
    "models.ranking.saving": "Saving…",
    "models.ranking.saved": "Ranking weights saved.",
    "models.ranking.saveError": "Could not save ranking",
    "models.ranking.reset": "Defaults (90 / 5 / 5)",
    "models.ranking.loading": "Loading chat settings…",
    "settings.title": "Settings",
    "settings.activePostgresEnv": "Active environment (target for upload & index)",
    "settings.vectorBackend": "Vector database",
    "settings.vectorBackend.postgres": "PostgreSQL (pgvector)",
    "settings.vectorBackend.sqlite": "SQLite (embedded, no server)",
    "settings.vectorBackend.qdrant": "Qdrant (embedded, local folder)",
    "settings.sqliteFilePath": "SQLite file (optional)",
    "settings.sqliteFilePathPlaceholder": "Empty = auto under ~/RAGIngestStudio/vector_sqlite/<environment-id>.sqlite",
    "settings.qdrantLocalPath": "Qdrant storage folder (optional)",
    "settings.qdrantLocalPathPlaceholder": "Empty = auto under ~/RAGIngestStudio/vector_qdrant/<environment-id>/",
    "settings.envName": "Environment display name",
    "settings.addPostgresEnv": "Add environment",
    "settings.removePostgresEnv": "Remove active environment",
    "settings.dbHost": "DB Host",
    "settings.dbPort": "DB Port",
    "settings.dbName": "DB Name",
    "settings.dbSchema": "Postgres schema",
    "settings.dbUser": "DB User",
    "settings.dbPassword": "DB Password",
    "settings.vectorTable": "Vector Table Name",
    "settings.chunkSize": "Chunk Size",
    "settings.chunkOverlap": "Chunk overlap (%)",
    "settings.embeddingModel": "Embedding Model",
    "settings.embeddingModelHint": "Only models with 384 dimensions (compatible with Qdrant embedded).",
    "settings.storeMarkdown": "Store Markdown",
    "settings.save": "Save Settings",
    "settings.connectionTest": "Connection Test",
    "settings.connectionTestRunning": "Testing …",
    "settings.connectionTestRunningDetail": "Checking Postgres and preparing the vector schema …",
    "settings.connectionTestUsesForm":
      "The test uses the values in this form (same as in pgAdmin). On success they are saved.",
    "settings.passwordKeepHint":
      "Password: type a new one and Save to store it. Leaving the field empty keeps the last saved password (it is not overwritten with blank).",
    "settings.connectionTestResponse": "Response (connection test / error)",
    "settings.loading": "Loading settings...",
    "settings.loadError":
      "API unreachable (documentApi on port 8000?). Showing default settings — start the backend and reload the app.",
    "settings.connectionTestError":
      "Connection test failed (network, timeout, or Postgres). Check settings and try again.",
    "settings.saved": "Settings saved. Please run Connection Test again.",
    "settings.testFirst": "Please run Connection Test first.",
    "settings.language": "Language",
    "jobs.title": "Job Events",
    "corpus.title": "Corpus Viewer",
    "corpus.saveAndReindex": "Save and Reindex",
    "corpus.close": "Close",
  },
} as const;

type TranslationKey = keyof (typeof translations)["de"];

const STORAGE_KEY = "rag-ingest-locale";

function getInitialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "de" || stored === "en") return stored;
  } catch {}
  return navigator.language.startsWith("de") ? "de" : "en";
}

export function useI18n() {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    try {
      localStorage.setItem(STORAGE_KEY, newLocale);
    } catch {}
  }, []);

  const t = useCallback(
    (key: TranslationKey, ...args: string[]): string => {
      let text: string = translations[locale][key] ?? key;
      args.forEach((arg, i) => {
        text = text.replace(`{${i}}`, arg);
      });
      return text;
    },
    [locale]
  );

  return useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
}
