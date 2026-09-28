export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export type ChatLocale = "de" | "en";

export interface ChatRequest {
  message: string;
  history: ChatMessage[];
  language?: ChatLocale;
  clientSource?: string;
}

export interface ChatResponse {
  answer: string;
  contextChunks: ContextChunk[];
  encryptedPayload: string;
  requestId?: string;
  metrics?: {
    elapsedMs?: number;
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    tokensPerSecond?: number;
  };
}

export interface ChatFeedbackRequest {
  helpful?: boolean;
  rating?: 1 | 2 | 3 | 4 | 5;
  comment?: string;
}

export interface ChatFeedbackRecord {
  feedbackId: string;
  requestId: string;
  helpful?: boolean | null;
  rating?: number | null;
  comment?: string | null;
  createdAt: number;
}

export interface ContextChunk {
  text: string;
  documentId: string;
  fileName: string;
  chunkIndex: number;
  sourcePath?: string;
  source?: string;
  similarity: number;
}

export interface ChatSettings {
  llmApiKey: string;
  llmBaseUrl: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  topK: number;
  /** Relative weight for embedding similarity in retrieval rerank (normalized at runtime). */
  rerankSimilarityWeight: number;
  /** Relative weight for exact token overlap (sensitive to word forms / tense). */
  rerankLexicalWeight: number;
  /** Relative weight for numeric string overlap. */
  rerankNumericWeight: number;
  systemPrompt: string;
  encryptionKey: string;
}
