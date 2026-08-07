# Validation Report

## Archetype

Tool-only MCP server mounted inside a FastAPI application.

## Passed checks

- Python syntax compilation passed for `app/`, `tests/`, and `download_ephe.py`.
- Unit tests passed: `15 passed`.
- The calculation test confirmed:
  - 12 Regiomontanus house cusps are returned.
  - `America/New_York` resolves to UTC-4 on August 6, 2026.
  - fixed-offset conversions safely roll UTC dates backward and forward across calendar boundaries.
  - non-Regiomontanus house systems are rejected.
  - Swiss Ephemeris path resolution is rooted at the project directory when `SWEPH_PATH` is unset or relative.
- MCP registration confirmed the public tool name is `calculate_chart`.
- FastAPI integration was exercised with a protocol stub:
  - `GET /health` returned 200.
  - authenticated `POST /mcp` reached the MCP protocol handler with no redirect.
  - `POST /chart` returned 200 and 12 cusps.
- The exact local startup command was exercised: `uvicorn app.main:app --reload --port 8000`.
  - `GET /health` returned 200.
  - unauthenticated `POST /mcp` returned 401.
  - bearer-authenticated malformed MCP POST reached protocol validation and returned 400.
- Bearer authentication middleware was exercised:
  - missing `MCP_API_KEY` returns 503 by default instead of serving an unauthenticated MCP endpoint.
  - missing token returned 401.
  - the configured bearer token passed the auth middleware.
- `GET /ready` returns 200 with all required ephemeris files present.
- Docker build succeeds and runs `python download_ephe.py` during image creation.
- `download_ephe.py` can copy files from a local Swiss Ephemeris checkout via
  `SWISSEPH_SOURCE_DIR` or sibling `../swisseph-master/ephe`, then falls back to
  remote downloads.
- Docker container smoke test passed:
  - Uvicorn listened on `0.0.0.0:10000`.
  - `GET /health` returned 200.
  - unauthenticated `POST /mcp` returned 401.
  - bearer-authenticated malformed MCP POST reached protocol validation and returned 400.

## Data-file status

Present:

- `ephe/seas_18.se1`
- `ephe/semo_18.se1`
- `ephe/sepl_18.se1`

The Dockerfile downloads the same three files at build time and sets
`SWEPH_PATH=/app/ephe` plus `REQUIRE_EPHE_FILES=true`.

## Checks not run

- Public HTTPS deployment and OAuth were not exercised.
