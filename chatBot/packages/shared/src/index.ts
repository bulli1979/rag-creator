export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export type ChatLocale = "de" | "en";

export interface ChatRequest {
  message: string;
  history: ChatMessage[];
  language?: ChatLocale;
}

export interface ChatResponse {
  answer: string;
  contextChunks: ContextChunk[];
  encryptedPayload: string;
  metrics?: {
    elapsedMs?: number;
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    tokensPerSecond?: number;
  };
}

export interface ContextChunk {
  text: string;
  documentId: string;
  fileName: string;
  chunkIndex: number;
  sourcePath?: string;
  source?: string;
  sourceId?: string;
  canonicalLocation?: string;
  corpusVersion?: string;
  instrument?: string;
  category?: string;
  authority?: string;
  status?: string;
  similarity: number;
  retrievalScore?: number;
}

export interface ChatSettings {
  llmApiKey: string;
  llmBaseUrl: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  topK: number;
  maxChunksPerSource: number;
  minEvidenceSimilarity: number;
  systemPrompt: string;
  encryptionKey: string;
}
