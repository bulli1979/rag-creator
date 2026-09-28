import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export interface ConnectionConfig {
  apiBaseUrl: string;
  apiKey: string;
}

interface ConnectionContextValue {
  reopenConnectionSetup: () => void;
}

const ConnectionContext = createContext<ConnectionContextValue>({
  reopenConnectionSetup: () => {}
});

export function useConnection(): ConnectionContextValue {
  return useContext(ConnectionContext);
}

interface ConnectionGateProps {
  children: ReactNode;
}

export default function ConnectionGate({ children }: ConnectionGateProps) {
  const [ready, setReady] = useState(false);
  const [checking, setChecking] = useState(true);
  const [apiBaseUrl, setApiBaseUrl] = useState("http://localhost:8000");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);

  const loadStored = useCallback(async () => {
    setChecking(true);
    setError("");
    try {
      const stored = await window.chatApi.connectionGet();
      if (stored?.apiBaseUrl && stored.apiKey) {
        setApiBaseUrl(stored.apiBaseUrl);
        setApiKey(stored.apiKey);
        const test = await window.chatApi.connectionTest(stored);
        if (test.ok) {
          await window.chatApi.connectionSave(stored);
          setReady(true);
          return;
        }
        setError(test.message);
      }
      setReady(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setReady(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void loadStored();
  }, [loadStored]);

  const reopenConnectionSetup = useCallback(() => {
    setReady(false);
    void loadStored();
  }, [loadStored]);

  async function handleSave(): Promise<void> {
    setTesting(true);
    setError("");
    try {
      const config = { apiBaseUrl: apiBaseUrl.trim(), apiKey: apiKey.trim() };
      const test = await window.chatApi.connectionTest(config);
      if (!test.ok) {
        setError(test.message);
        return;
      }
      await window.chatApi.connectionSave(config);
      setReady(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTesting(false);
    }
  }

  if (checking) {
    return (
      <div className="connection-gate">
        <p>Verbindung wird geprüft …</p>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="connection-gate">
        <div className="connection-card">
          <h1>API-Verbindung</h1>
          <p>Bitte URL und API-Key der documentApi eingeben.</p>
          <label className="connection-field">
            <span>API-URL</span>
            <input
              value={apiBaseUrl}
              onChange={(e) => setApiBaseUrl(e.target.value)}
              placeholder="http://localhost:8000"
            />
          </label>
          <label className="connection-field">
            <span>API-Key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="rag_..."
            />
          </label>
          {error && <p className="connection-error">{error}</p>}
          <button type="button" className="send-btn" disabled={testing} onClick={() => void handleSave()}>
            {testing ? "Prüfe …" : "Speichern & verbinden"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <ConnectionContext.Provider value={{ reopenConnectionSetup }}>
      {children}
    </ConnectionContext.Provider>
  );
}
