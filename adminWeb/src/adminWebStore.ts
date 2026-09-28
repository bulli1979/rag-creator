/** Client-ID + Sync der Admin-Web-Daten mit dem Backend (`/api/admin-web/*`). */

const CLIENT_ID_KEY = "rag_admin_web_client_id_v1";

export type AdminWebConnectionRow = {
  connectionId: string;
  clientId: string;
  name: string;
  apiBaseUrl: string;
  apiKey: string;
  isDefault: boolean;
  createdAt: number;
  updatedAt: number;
};

export function getOrCreateAdminWebClientId(): string {
  try {
    const existing = localStorage.getItem(CLIENT_ID_KEY)?.trim();
    if (existing) {
      return existing;
    }
    const id = crypto.randomUUID();
    localStorage.setItem(CLIENT_ID_KEY, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

function adminWebHeaders(apiKey: string): Record<string, string> {
  return {
    "X-API-Key": apiKey,
    "X-Admin-Web-Client-Id": getOrCreateAdminWebClientId(),
    "Content-Type": "application/json"
  };
}

export async function registerAdminWebClient(
  baseUrl: string,
  apiKey: string
): Promise<void> {
  const url = baseUrl.replace(/\/$/, "");
  await fetch(`${url}/api/admin-web/clients`, {
    method: "POST",
    headers: adminWebHeaders(apiKey),
    body: JSON.stringify({
      clientId: getOrCreateAdminWebClientId(),
      label: "admin-web",
      userAgent: typeof navigator !== "undefined" ? navigator.userAgent : null
    })
  });
}

export async function syncConnectionToBackend(
  baseUrl: string,
  apiKey: string,
  connection: { apiBaseUrl: string; apiKey: string; name?: string }
): Promise<AdminWebConnectionRow | null> {
  const url = baseUrl.replace(/\/$/, "");
  try {
    await registerAdminWebClient(url, apiKey);
    const response = await fetch(`${url}/api/admin-web/connections`, {
      method: "PUT",
      headers: adminWebHeaders(apiKey),
      body: JSON.stringify({
        name: connection.name ?? "default",
        apiBaseUrl: connection.apiBaseUrl,
        apiKey: connection.apiKey,
        isDefault: true
      })
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as AdminWebConnectionRow;
  } catch {
    return null;
  }
}

export async function loadDefaultConnectionFromBackend(
  baseUrl: string,
  apiKey: string
): Promise<{ apiBaseUrl: string; apiKey: string } | null> {
  const url = baseUrl.replace(/\/$/, "");
  try {
    await registerAdminWebClient(url, apiKey);
    const response = await fetch(`${url}/api/admin-web/connections`, {
      headers: {
        "X-API-Key": apiKey,
        "X-Admin-Web-Client-Id": getOrCreateAdminWebClientId()
      }
    });
    if (!response.ok) {
      return null;
    }
    const rows = (await response.json()) as AdminWebConnectionRow[];
    const preferred = rows.find((r) => r.isDefault) ?? rows[0];
    if (!preferred) {
      return null;
    }
    return { apiBaseUrl: preferred.apiBaseUrl, apiKey: preferred.apiKey };
  } catch {
    return null;
  }
}

export async function saveAdminWebPreference(
  baseUrl: string,
  apiKey: string,
  prefKey: string,
  prefValue: unknown
): Promise<boolean> {
  const url = baseUrl.replace(/\/$/, "");
  try {
    const response = await fetch(`${url}/api/admin-web/preferences`, {
      method: "PUT",
      headers: adminWebHeaders(apiKey),
      body: JSON.stringify({ prefKey, prefValue })
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function logAdminWebEvent(
  baseUrl: string,
  apiKey: string,
  eventType: string,
  payload?: Record<string, unknown>
): Promise<void> {
  const url = baseUrl.replace(/\/$/, "");
  try {
    await fetch(`${url}/api/admin-web/events`, {
      method: "POST",
      headers: adminWebHeaders(apiKey),
      body: JSON.stringify({ eventType, payload: payload ?? null })
    });
  } catch {
    // non-blocking
  }
}
