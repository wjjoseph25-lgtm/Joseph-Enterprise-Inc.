import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

const PORT = Number(process.env.PORT || 8787);
const MCP_PATH = "/mcp";
const STORE_PATH = resolve(
  process.env.LOCATION_STORE_PATH ||
    `${homedir()}/.codex/user-environment-context-http-location.json`
);
const UPDATE_TOKEN = process.env.LOCATION_UPDATE_TOKEN || "";
const GEOCODER_BASE_URL =
  process.env.GEOCODER_BASE_URL || "https://nominatim.openstreetmap.org";
const GEOCODER_USER_AGENT =
  process.env.GEOCODER_USER_AGENT ||
  "user-environment-context-mcp/0.1.0 (local development)";

function localTimestamp() {
  const now = new Date();
  const offsetMinutes = -now.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hh = String(Math.floor(absolute / 60)).padStart(2, "0");
  const mm = String(absolute % 60).padStart(2, "0");
  return new Date(now.getTime() + offsetMinutes * 60_000)
    .toISOString()
    .replace("Z", `${sign}${hh}:${mm}`);
}

function timezone() {
  return process.env.USER_ENV_TIMEZONE || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

function validCoordinate(value, min, max) {
  return Number.isFinite(value) && value >= min && value <= max;
}

async function readStoredLocation() {
  if (!existsSync(STORE_PATH)) {
    return null;
  }
  const payload = JSON.parse(await readFile(STORE_PATH, "utf8"));
  const latitude = Number(payload.latitude);
  const longitude = Number(payload.longitude);
  if (!validCoordinate(latitude, -90, 90) || !validCoordinate(longitude, -180, 180)) {
    return null;
  }
  return {
    latitude,
    longitude,
    accuracy_meters: Number.isFinite(Number(payload.accuracy_meters))
      ? Number(payload.accuracy_meters)
      : null,
    location_updated_at: typeof payload.updated_at === "string" ? payload.updated_at : null,
    coordinate_source: typeof payload.source === "string" ? payload.source : "browser_geolocation",
    geocoder: payload.geocoder ?? null
  };
}

function summarizeAddress(geocoderPayload) {
  if (!geocoderPayload || typeof geocoderPayload !== "object") {
    return null;
  }
  const address = geocoderPayload.address && typeof geocoderPayload.address === "object"
    ? geocoderPayload.address
    : {};
  return {
    display_name: typeof geocoderPayload.display_name === "string"
      ? geocoderPayload.display_name
      : null,
    house_number: address.house_number ?? null,
    road: address.road ?? address.pedestrian ?? address.footway ?? address.path ?? null,
    neighbourhood: address.neighbourhood ?? address.suburb ?? null,
    city: address.city ?? address.town ?? address.village ?? address.hamlet ?? null,
    county: address.county ?? null,
    state: address.state ?? null,
    postcode: address.postcode ?? null,
    country: address.country ?? null,
    country_code: address.country_code ?? null
  };
}

async function reverseGeocode(latitude, longitude) {
  const url = new URL("/reverse", GEOCODER_BASE_URL);
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("lat", String(latitude));
  url.searchParams.set("lon", String(longitude));
  url.searchParams.set("addressdetails", "1");
  url.searchParams.set("zoom", "18");

  const response = await fetch(url, {
    headers: {
      "accept": "application/json",
      "user-agent": GEOCODER_USER_AGENT
    }
  });
  if (!response.ok) {
    throw new Error(`Reverse geocoder returned HTTP ${response.status}.`);
  }
  return summarizeAddress(await response.json());
}

async function writeStoredLocation(payload) {
  const latitude = Number(payload.latitude);
  const longitude = Number(payload.longitude);
  if (!validCoordinate(latitude, -90, 90) || !validCoordinate(longitude, -180, 180)) {
    throw new Error("latitude/longitude are invalid.");
  }

  let geocoder = null;
  let geocoder_error = null;
  try {
    geocoder = await reverseGeocode(latitude, longitude);
  } catch (error) {
    geocoder_error = error instanceof Error ? error.message : String(error);
  }

  const next = {
    latitude,
    longitude,
    accuracy_meters: Number.isFinite(Number(payload.accuracy_meters))
      ? Number(payload.accuracy_meters)
      : null,
    source: "browser_geolocation",
    updated_at: new Date().toISOString(),
    geocoder,
    geocoder_error
  };
  await mkdir(dirname(STORE_PATH), { recursive: true });
  await writeFile(STORE_PATH, JSON.stringify(next, null, 2));
  return next;
}

async function readJsonRequest(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  if (chunks.length === 0) {
    return {};
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function sendJson(res, status, payload) {
  res.writeHead(status, {
    "content-type": "application/json",
    "access-control-allow-origin": "*"
  });
  res.end(JSON.stringify(payload));
}

function capturePage() {
  const tokenInput = UPDATE_TOKEN
    ? `<label>Update token <input id="token" autocomplete="off" placeholder="Required"></label>`
    : "";
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>User Environment Context</title>
  <style>
    body { font: 16px system-ui, sans-serif; margin: 2rem; max-width: 720px; line-height: 1.45; }
    button { font: inherit; padding: 0.65rem 0.9rem; }
    input { font: inherit; display: block; margin: 0.4rem 0 1rem; width: 100%; max-width: 420px; padding: 0.5rem; }
    pre { background: #f4f4f5; padding: 1rem; overflow: auto; }
  </style>
</head>
<body>
  <h1>User Environment Context</h1>
  <p>Use this page to refresh the GPS coordinates returned by the ChatGPT MCP tool.</p>
  ${tokenInput}
  <button id="capture">Update current location</button>
  <pre id="out">Waiting.</pre>
  <script>
    const out = document.getElementById("out");
    document.getElementById("capture").addEventListener("click", () => {
      if (!navigator.geolocation) {
        out.textContent = "Browser geolocation is not available.";
        return;
      }
      out.textContent = "Requesting location permission...";
      navigator.geolocation.getCurrentPosition(async (position) => {
        const body = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_meters: position.coords.accuracy
        };
        const headers = { "content-type": "application/json" };
        const token = document.getElementById("token")?.value;
        if (token) headers.authorization = "Bearer " + token;
        const response = await fetch("/api/location", {
          method: "POST",
          headers,
          body: JSON.stringify(body)
        });
        const json = await response.json();
        out.textContent = JSON.stringify(json, null, 2);
      }, (error) => {
        out.textContent = error.message;
      }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 });
    });
  </script>
</body>
</html>`;
}

function createMcpServer() {
  const server = new McpServer({
    name: "user-environment-context",
    version: "0.1.0"
  });

  server.registerTool(
    "get_user_environment_context",
    {
      title: "Get user environment context",
      description:
        "Use this when the user asks for their current timestamp, timezone, or previously captured browser GPS coordinates.",
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
        idempotentHint: true
      }
    },
    async () => {
      const storedLocation = await readStoredLocation();
      const structuredContent = {
        timestamp: localTimestamp(),
        timezone: timezone(),
        latitude: storedLocation?.latitude ?? null,
        longitude: storedLocation?.longitude ?? null,
        coordinates_available: Boolean(storedLocation),
        coordinate_source: storedLocation?.coordinate_source ?? "not_captured",
        accuracy_meters: storedLocation?.accuracy_meters ?? null,
        location_updated_at: storedLocation?.location_updated_at ?? null,
        address: storedLocation?.geocoder ?? null,
        capture_url: "/capture"
      };
      return {
        content: [{ type: "text", text: JSON.stringify(structuredContent) }],
        structuredContent
      };
    }
  );

  return server;
}

createServer(async (req, res) => {
  if (!req.url) {
    res.writeHead(400).end("Missing URL");
    return;
  }
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const isMcpRoute = url.pathname === MCP_PATH || url.pathname.startsWith(`${MCP_PATH}/`);

  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "POST, GET, DELETE, OPTIONS",
      "access-control-allow-headers": "content-type, mcp-session-id, authorization",
      "access-control-expose-headers": "Mcp-Session-Id"
    });
    res.end();
    return;
  }

  if (req.method === "GET" && url.pathname === "/") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end(`User Environment Context MCP server. Open /capture to refresh location, connect ChatGPT to ${MCP_PATH}.`);
    return;
  }

  if (req.method === "GET" && url.pathname === "/capture") {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(capturePage());
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/location") {
    if (UPDATE_TOKEN && req.headers.authorization !== `Bearer ${UPDATE_TOKEN}`) {
      sendJson(res, 401, { ok: false, error: "Missing or invalid update token." });
      return;
    }
    try {
      const saved = await writeStoredLocation(await readJsonRequest(req));
      sendJson(res, 200, { ok: true, location: saved });
    } catch (error) {
      sendJson(res, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
    }
    return;
  }

  if (isMcpRoute && req.method && ["GET", "POST", "DELETE"].includes(req.method)) {
    res.setHeader("access-control-allow-origin", "*");
    res.setHeader("access-control-expose-headers", "Mcp-Session-Id");

    const server = createMcpServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true
    });

    res.on("close", () => {
      transport.close();
      server.close();
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res);
    } catch (error) {
      console.error("Failed to handle MCP request:", error);
      if (!res.headersSent) {
        res.writeHead(500).end("Internal server error");
      }
    }
    return;
  }

  res.writeHead(404).end("Not Found");
}).listen(PORT, () => {
  console.log(`User Environment Context MCP server listening on http://localhost:${PORT}${MCP_PATH}`);
  console.log(`Capture page: http://localhost:${PORT}/capture`);
});
