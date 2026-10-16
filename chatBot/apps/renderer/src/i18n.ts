import { useState, useCallback, useMemo } from "react";

export type Locale = "de" | "en";

const translations = {
  de: {
    "app.title": "RAG Chatbot",
    "app.subtitle": "Dokumentenbasierte KI-Assistenz",
    "sidebar.llmConfig": "LLM Konfiguration",
    "sidebar.apiKey": "API Key",
    "sidebar.baseUrl": "Base URL",
    "sidebar.model": "Modell",
    "sidebar.temperature": "Temperatur",
    "sidebar.maxTokens": "Max Tokens",
    "sidebar.topK": "Top K (Kontext-Chunks)",
    "sidebar.maxChunksPerSource": "Max. Chunks pro Quelle",
    "sidebar.minEvidenceSimilarity": "Mindestähnlichkeit für Belege",
    "sidebar.systemPrompt": "System Prompt",
    "sidebar.saveSettings": "Einstellungen speichern",
    "sidebar.clearChat": "Chat leeren",
    "sidebar.language": "Sprache",
    "status.connected": "API verbunden",
    "status.disconnected": "API nicht erreichbar",
    "chat.placeholder": "Schreibe eine Nachricht... (Enter zum Senden, Shift+Enter für Zeilenumbruch)",
    "chat.emptyState": "Stelle eine Frage zu deinen Dokumenten",
    "chat.you": "Du",
    "chat.ai": "KI",
    "chat.sourcesUsed": "Quellen verwendet",
    "chat.relevance": "Relevanz",
    "chat.metrics": "Antwort-Metriken",
    "chat.metrics.elapsed": "Dauer",
    "chat.metrics.promptTokens": "Prompt Tokens",
    "chat.metrics.completionTokens": "Output Tokens",
    "chat.metrics.totalTokens": "Total Tokens",
    "chat.metrics.tokensPerSecond": "Tokens/s",
    "chat.error": "Fehler bei der Anfrage",
    "chat.copy": "Ergebnis kopieren",
    "chat.feedback.helpful": "Hilfreich",
    "chat.feedback.notHelpful": "Nicht hilfreich",
    "chat.feedback.commentLabel": "Optionaler Kommentar zum Feedback",
    "chat.feedback.commentPlaceholder": "Was war gut oder was fehlte?",
    "chat.feedback.thanks": "Danke für dein Feedback.",
    "chat.feedback.submitted": "Feedback gespeichert.",
    "chat.feedback.error": "Feedback konnte nicht gespeichert werden",
    "notify.settingsSaved": "Einstellungen gespeichert.",
    "notify.error": "Fehler",
  },
  en: {
    "app.title": "RAG Chatbot",
    "app.subtitle": "Document-based AI Assistant",
    "sidebar.llmConfig": "LLM Configuration",
    "sidebar.apiKey": "API Key",
    "sidebar.baseUrl": "Base URL",
    "sidebar.model": "Model",
    "sidebar.temperature": "Temperature",
    "sidebar.maxTokens": "Max Tokens",
    "sidebar.topK": "Top K (Context Chunks)",
    "sidebar.maxChunksPerSource": "Max chunks per source",
    "sidebar.minEvidenceSimilarity": "Minimum evidence similarity",
    "sidebar.systemPrompt": "System Prompt",
    "sidebar.saveSettings": "Save Settings",
    "sidebar.clearChat": "Clear Chat",
    "sidebar.language": "Language",
    "status.connected": "API connected",
    "status.disconnected": "API not reachable",
    "chat.placeholder": "Type a message... (Enter to send, Shift+Enter for line break)",
    "chat.emptyState": "Ask a question about your documents",
    "chat.you": "You",
    "chat.ai": "AI",
    "chat.sourcesUsed": "sources used",
    "chat.relevance": "Relevance",
    "chat.metrics": "Response metrics",
    "chat.metrics.elapsed": "Latency",
    "chat.metrics.promptTokens": "Prompt tokens",
    "chat.metrics.completionTokens": "Output tokens",
    "chat.metrics.totalTokens": "Total tokens",
    "chat.metrics.tokensPerSecond": "Tokens/s",
    "chat.error": "Request error",
    "chat.copy": "Copy answer",
    "chat.feedback.helpful": "Helpful",
    "chat.feedback.notHelpful": "Not helpful",
    "chat.feedback.commentLabel": "Optional feedback comment",
    "chat.feedback.commentPlaceholder": "What worked well or what was missing?",
    "chat.feedback.thanks": "Thanks for your feedback.",
    "chat.feedback.submitted": "Feedback saved.",
    "chat.feedback.error": "Could not save feedback",
    "notify.settingsSaved": "Settings saved.",
    "notify.error": "Error",
  },
} as const;

type TranslationKey = keyof (typeof translations)["de"];

const STORAGE_KEY = "rag-chat-locale";

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
