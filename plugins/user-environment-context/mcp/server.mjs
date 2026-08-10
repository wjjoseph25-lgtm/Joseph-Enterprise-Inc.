#!/usr/bin/env node

import readline from "node:readline";
import { execFile } from "node:child_process";
import { dirname, join } from "node:path";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";

const serverInfo = {
  name: "user-environment-context",
  version: "0.1.0"
};

const tool = {
  name: "get_user_environment_context",
  description:
    "Returns the user's current local timestamp, timezone, and GPS coordinates when available from environment variables or macOS Location Services.",
  inputSchema: {
    type: "object",
    properties: {},
    additionalProperties: false
  },
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    openWorldHint: false
  }
};

function parseCoordinate(name, min, max) {
  const raw = process.env[name];
  if (raw == null || raw.trim() === "") {
    return undefined;
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${name} must be a number between ${min} and ${max}.`);
  }
  return value;
}

function localTimestamp() {
  const now = new Date();
  const offsetMinutes = -now.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hh = String(Math.floor(absolute / 60)).padStart(2, "0");
  const mm = String(absolute % 60).padStart(2, "0");
  const local = new Date(now.getTime() + offsetMinutes * 60_000)
    .toISOString()
    .replace("Z", `${sign}${hh}:${mm}`);
  return local;
}

function runLocationHelper() {
  const mcpDir = dirname(fileURLToPath(import.meta.url));
  const binaryPath = join(mcpDir, "bin", "macos-location");
  const scriptPath = join(mcpDir, "macos-location.swift");
  const command = existsSync(binaryPath) ? binaryPath : "/usr/bin/swift";
  const args = existsSync(binaryPath) ? [] : [scriptPath];
  return new Promise((resolve) => {
    execFile(
      command,
      args,
      { timeout: 20_000, maxBuffer: 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          const detail = stderr.trim() || err.message;
          resolve({
            latitude: undefined,
            longitude: undefined,
            source: "macos_location_services_unavailable",
            error: detail.includes("kCLErrorDomain error 1")
              ? "macOS denied Location Services for this command-line helper. Enable Location Services for the terminal/Codex host, or set USER_ENV_LATITUDE and USER_ENV_LONGITUDE in the MCP environment."
              : detail
          });
          return;
        }

        try {
          const payload = JSON.parse(stdout);
          resolve({
            latitude: payload.latitude,
            longitude: payload.longitude,
            source: "macos_location_services",
            accuracy_meters: payload.accuracy_meters
          });
        } catch (parseErr) {
          resolve({
            latitude: undefined,
            longitude: undefined,
            source: "macos_location_services_invalid_response",
            error: parseErr instanceof Error ? parseErr.message : String(parseErr)
          });
        }
      }
    );
  });
}

function readLocationFile() {
  const path = join(homedir(), ".codex", "user-location.json");
  if (!existsSync(path)) {
    return undefined;
  }

  const payload = JSON.parse(readFileSync(path, "utf8"));
  const latitude = Number(payload.latitude);
  const longitude = Number(payload.longitude);
  if (
    !Number.isFinite(latitude) ||
    latitude < -90 ||
    latitude > 90 ||
    !Number.isFinite(longitude) ||
    longitude < -180 ||
    longitude > 180
  ) {
    return undefined;
  }

  return {
    latitude,
    longitude,
    source: "local_location_file",
    accuracy_meters: Number.isFinite(Number(payload.accuracy_meters))
      ? Number(payload.accuracy_meters)
      : undefined,
    updated_at: typeof payload.updated_at === "string" ? payload.updated_at : undefined
  };
}

async function getCoordinates() {
  const latitude = parseCoordinate("USER_ENV_LATITUDE", -90, 90);
  const longitude = parseCoordinate("USER_ENV_LONGITUDE", -180, 180);
  if (latitude != null && longitude != null) {
    return { latitude, longitude, source: "environment_variables" };
  }

  const fileCoordinates = readLocationFile();
  if (fileCoordinates != null) {
    return fileCoordinates;
  }

  if (process.platform === "darwin") {
    return await runLocationHelper();
  }

  return {
    latitude: undefined,
    longitude: undefined,
    source: "not_supplied_by_host"
  };
}

async function getEnvironmentContext() {
  const coordinates = await getCoordinates();
  const timezone =
    process.env.USER_ENV_TIMEZONE ||
    Intl.DateTimeFormat().resolvedOptions().timeZone ||
    "UTC";

  const structuredContent = {
    timestamp: process.env.USER_ENV_TIMESTAMP || localTimestamp(),
    timezone,
    latitude: coordinates.latitude ?? null,
    longitude: coordinates.longitude ?? null,
    coordinates_available: coordinates.latitude != null && coordinates.longitude != null,
    coordinate_source: coordinates.source
  };
  if (coordinates.accuracy_meters != null) {
    structuredContent.accuracy_meters = coordinates.accuracy_meters;
  }
  if (coordinates.updated_at != null) {
    structuredContent.location_updated_at = coordinates.updated_at;
  }
  if (coordinates.error != null) {
    structuredContent.location_error = coordinates.error;
  }

  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(structuredContent)
      }
    ],
    structuredContent
  };
}

function result(id, value) {
  process.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id, result: value })}\n`);
}

function error(id, code, message) {
  process.stdout.write(
    `${JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } })}\n`
  );
}

async function handle(message) {
  const { id, method, params } = message;

  try {
    if (method === "initialize") {
      result(id, {
        protocolVersion: params?.protocolVersion || "2024-11-05",
        capabilities: {
          tools: {}
        },
        serverInfo
      });
      return;
    }

    if (method === "notifications/initialized") {
      return;
    }

    if (method === "tools/list") {
      result(id, { tools: [tool] });
      return;
    }

    if (method === "tools/call") {
      if (params?.name !== tool.name) {
        error(id, -32602, `Unknown tool: ${params?.name}`);
        return;
      }
      result(id, await getEnvironmentContext());
      return;
    }

    error(id, -32601, `Method not found: ${method}`);
  } catch (err) {
    error(id, -32000, err instanceof Error ? err.message : String(err));
  }
}

const rl = readline.createInterface({
  input: process.stdin,
  terminal: false
});

rl.on("line", (line) => {
  if (!line.trim()) {
    return;
  }
  try {
    void handle(JSON.parse(line));
  } catch {
    error(null, -32700, "Parse error");
  }
});
