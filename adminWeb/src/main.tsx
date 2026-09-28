import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installBrowserRagApi } from "./browserRagApi";
import { getOrCreateAdminWebClientId } from "./adminWebStore";
import App from "./App";
import ConnectionGate from "./ConnectionGate";
import "./styles.css";

getOrCreateAdminWebClientId();
installBrowserRagApi();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root-Element fuer React wurde nicht gefunden.");
}

createRoot(rootElement).render(
  <StrictMode>
    <ConnectionGate>
      <App />
    </ConnectionGate>
  </StrictMode>
);
