# Orora Swiss Ephemeris MCP Server

A tool-only MCP server and FastAPI service for calculating tropical Regiomontanus horary charts with Swiss Ephemeris.

## Endpoints

- `GET /health` — liveness check
- `GET /ready` — verifies all required `.se1` files are present
- `POST /chart` — REST compatibility endpoint
- `/mcp` — Streamable HTTP MCP endpoint

The MCP app is configured with `streamable_http_path="/"` before it is mounted at `/mcp`. This avoids accidentally publishing the tool at `/mcp/mcp`.

## Features

- Swiss Ephemeris planetary positions
- All 12 Regiomontanus house cusps
- Ascendant, Midheaven, ARMC, and Vertex
- IANA timezone support through Python `zoneinfo`
- DST gap detection and `fold` support for ambiguous fall-back times
- Fixed UTC offset compatibility mode
- MCP read-only/idempotent tool annotations
- Bearer-token authentication for MCP requests
- Request logging and a basic per-process rate limiter
- Public-host allowlists for MCP DNS-rebinding protection

## Project structure

```text
orora-ephemeris-server/
├── app/
│   ├── __init__.py
│   ├── ephemeris.py
│   ├── main.py
│   ├── mcp_server.py
│   └── schemas.py
├── ephe/
├── tests/
│   └── test_ephemeris.py
├── .env.example
├── Dockerfile
└── requirements.txt
```

## Ephemeris files

The project expects Swiss Ephemeris data in the project-local `ephe/` directory
unless `SWEPH_PATH` points elsewhere. Relative `SWEPH_PATH` values are resolved
from the project root, not the process working directory:

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EPHE_PATH = os.getenv("SWEPH_PATH", str(PROJECT_ROOT / "ephe"))
```

For the 1800–2399 date range, the included setup uses:

- `sepl_18.se1` — planets
- `semo_18.se1` — Moon
- `seas_18.se1` — main asteroids, including Chiron support

Review the Swiss Ephemeris dual-license terms before activating a public service. A commercial/non-AGPL deployment generally requires the professional license.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

For MCP requests, set `MCP_API_KEY` in `.env` first. The server fails closed for
`/mcp` when `MCP_AUTH_REQUIRED=true` and no API key is configured.

Health check:

```bash
curl http://localhost:8000/health
```

REST calculation:

```bash
curl -X POST http://localhost:8000/chart \
  -H 'Content-Type: application/json' \
  -d '{
    "year": 2026,
    "month": 8,
    "day": 6,
    "hour": 16,
    "minute": 50,
    "second": 0,
    "timezone_name": "America/New_York",
    "latitude": 27.9506,
    "longitude": -82.4572,
    "house_system": "R"
  }'
```

MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

Connect the Inspector to:

```text
http://localhost:8000/mcp
```

Set `MCP_API_KEY` before making MCP requests, then send:

```text
Authorization: Bearer YOUR_KEY
```

## Docker

```bash
docker build -t orora-ephemeris .
docker run --rm -p 8000:10000 --env-file .env orora-ephemeris
```

The Docker build runs `python download_ephe.py`, sets `SWEPH_PATH=/app/ephe`,
and enables `REQUIRE_EPHE_FILES=true` inside the image.

## Public deployment

Before deployment:

1. Build from the Dockerfile so `python download_ephe.py` embeds all required `.se1` files in the image.
2. Set `MCP_API_KEY` to a long random secret or replace the simple bearer check with OAuth.
3. Set `MCP_ALLOWED_HOSTS` to the exact public hostname and its wildcard-port form.
4. Set `MCP_ALLOWED_ORIGINS` to only trusted browser origins that need direct access.
5. Put a managed rate limiter/API gateway in front of the service when using multiple workers.
6. Confirm that `POST https://your-domain.example/mcp` does not redirect.
7. Terminate TLS at the hosting platform or reverse proxy.

Example:

```dotenv
REQUIRE_EPHE_FILES=true
MCP_API_KEY=replace-with-a-long-random-value
MCP_AUTH_REQUIRED=true
MCP_ALLOWED_HOSTS=your-domain.example,your-domain.example:*
MCP_ALLOWED_ORIGINS=https://chatgpt.com
```

## Custom MCP connection

- **Name:** Orora Swiss Ephemeris
- **Server URL:** `https://your-domain.example/mcp`
- **Authentication:** Bearer token or your configured OAuth method

Do not configure an agent with a localhost URL; localhost is only for local testing.
