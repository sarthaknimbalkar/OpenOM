// Assemble a Buildout draft-source from stored config (endpoint + token). Returns null when Buildout
// is not configured, so the picker cleanly falls back to the on-device extractor. This is the only
// place that ties the pure connector (buildout.ts / buildout-http.ts) to the extension's storage.
import { getBuildoutConfig } from "../../../storage.js";
import { connectorSource, type DraftSource } from "../source.js";
import { makeBuildoutConnector } from "./buildout.js";
import { httpMcpBuildoutClient } from "./buildout-http.js";

/** Build a deterministic Buildout `DraftSource` for `ref`, or null if the connector isn't configured. */
export async function loadBuildoutSource(ref: string): Promise<DraftSource | null> {
  const cfg = await getBuildoutConfig();
  if (!cfg) return null;
  const client = httpMcpBuildoutClient(
    { endpoint: cfg.endpoint, toolName: cfg.toolName },
    async () => cfg.token,
  );
  return connectorSource(makeBuildoutConnector(client), ref);
}
