import { useCallback, useEffect, useState } from "react";
import type { ApiKeyListItem } from "./types/global";

export default function ApiKeysPanel() {
  const [keys, setKeys] = useState<ApiKeyListItem[]>([]);
  const [newLabel, setNewLabel] = useState("client");
  const [createdKey, setCreatedKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await window.ragApi.listApiKeys();
      setKeys(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleCreate(isAdmin: boolean): Promise<void> {
    setError("");
    setCreatedKey("");
    try {
      const created = await window.ragApi.createApiKey(newLabel.trim() || "client", isAdmin);
      setCreatedKey(created.apiKey);
      setNewLabel("client");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleRevoke(keyId: string): Promise<void> {
    setError("");
    try {
      await window.ragApi.revokeApiKey(keyId);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="api-keys-panel" style={{ gridColumn: "1 / -1", marginBottom: 16 }}>
      <h3>API-Schlüssel (Admin)</h3>
      <p className="upload-hint">Neue Client-Keys für Electron-Apps oder Web-Clients anlegen. Widerrufene Keys funktionieren nicht mehr.</p>
      <div className="button-row">
        <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="Label" />
        <button type="button" onClick={() => void handleCreate(false)}>
          Client-Key erstellen
        </button>
        <button type="button" onClick={() => void handleCreate(true)}>
          Admin-Key erstellen
        </button>
        <button type="button" onClick={() => void reload()} disabled={loading}>
          Aktualisieren
        </button>
      </div>
      {createdKey ? (
        <p className="connection-feedback connection-feedback--ok">
          Neuer Key (nur einmal sichtbar): <code>{createdKey}</code>
        </p>
      ) : null}
      {error ? <p className="connection-feedback connection-feedback--err">{error}</p> : null}
      <table className="data-table" style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th>Label</th>
            <th>Rolle</th>
            <th>Erstellt</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr key={key.keyId}>
              <td>{key.label}</td>
              <td>{key.isAdmin ? "Admin" : "Client"}</td>
              <td>{new Date(key.createdAt).toLocaleString()}</td>
              <td>{key.revokedAt ? "Widerrufen" : "Aktiv"}</td>
              <td>
                {!key.revokedAt ? (
                  <button type="button" onClick={() => void handleRevoke(key.keyId)}>
                    Widerrufen
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
