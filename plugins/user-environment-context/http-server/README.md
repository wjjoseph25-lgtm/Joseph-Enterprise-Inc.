# User Environment Context HTTP MCP Server

Deployable Streamable HTTP MCP server for ChatGPT.

## Run locally

```bash
npm install
npm start
```

Then open:

- `http://localhost:8787/capture` to grant browser geolocation and update stored coordinates.
- `http://localhost:8787/mcp` as the MCP endpoint.

## Environment

- `PORT`: server port, default `8787`.
- `LOCATION_STORE_PATH`: JSON file path for captured coordinates.
- `LOCATION_UPDATE_TOKEN`: optional bearer token required by `/api/location`.
- `USER_ENV_TIMEZONE`: optional timezone override.
- `GEOCODER_BASE_URL`: optional reverse geocoder base URL, default `https://nominatim.openstreetmap.org`.
- `GEOCODER_USER_AGENT`: user-agent sent to the geocoder. Set this to identify your app/contact for production.

## ChatGPT

For ChatGPT developer testing, expose this server over HTTPS and connect ChatGPT Plugins to:

```text
https://your-domain.example/mcp
```

The `/capture` page must also be reachable in a normal browser so the user can update GPS coordinates.

Captured coordinates are reverse geocoded with Nominatim and returned from `get_user_environment_context` as `address`.
