# User Environment Context

Local Codex plugin exposing one MCP tool:

- `get_user_environment_context`

The tool returns the local ISO timestamp and timezone. GPS coordinates are read from environment variables when provided:

- `USER_ENV_LATITUDE`
- `USER_ENV_LONGITUDE`
- `USER_ENV_TIMESTAMP` optional
- `USER_ENV_TIMEZONE` optional

On macOS, if the environment variables are absent, the tool falls back to CoreLocation and may prompt for Location Services permission.

## ChatGPT HTTP MCP server

For ChatGPT developer mode or deployment, use the Streamable HTTP server in `http-server/`.

```bash
cd /Users/winstinj.joseph/plugins/user-environment-context/http-server
npm install
npm start
```

Local endpoints:

- `http://localhost:8787/mcp`
- `http://localhost:8787/capture`

Expose `/mcp` over HTTPS for ChatGPT, and open `/capture` in a browser to refresh GPS coordinates.

The HTTP server also reverse geocodes captured GPS coordinates and returns an `address` object from `get_user_environment_context`.
