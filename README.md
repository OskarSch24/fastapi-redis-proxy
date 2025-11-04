# FastAPI Redis Proxy

Expose safe HTTP endpoints for RedisJSON access from n8n.

## Run locally

- Create a virtualenv and install requirements from `requirements.txt`.
- Start: `uvicorn app.main:app --host 0.0.0.0 --port 8080`.
- Health: GET `http://localhost:8080/health`.

### Quick test

- POST `http://localhost:8080/redis/command` with header `X-API-Key: <API_KEY>`
  and body `{ "command": "JSON.GET", "args": ["index:database_schema"] }`.
- POST `http://localhost:8080/redis/json-get` with header `X-API-Key: <API_KEY>`
  and body `{ "key": "doc:brand_brief:001" }`.

## Environment

See `ENV_VARS_EXAMPLE.md` for required variables.

## Deploy (Railway)

- New project → Deploy from GitHub (root `/`).
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Set env vars (Redis + API_KEY). Health check: `/health`.

### Environment (Railway)

Set the following variables in Railway → Variables:

- `REDIS_HOST` = your Redis Cloud host
- `REDIS_PORT` = your Redis Cloud port
- `REDIS_PASSWORD` = your Redis Cloud password
- `REDIS_TLS` = `true`
- `API_KEY` = a strong random key used by n8n
- `PYTHONUNBUFFERED` = `1`

### n8n Integration

- AI Tool (HTTP Tool): POST `${SERVICE_URL}/redis/command`
  - Headers: `X-API-Key: <API_KEY>`, `Content-Type: application/json`
  - Body: `{ "command": "JSON.GET", "args": ["index:database_schema"] }`
- Loop Query (HTTP Request): POST `${SERVICE_URL}/redis/json-get`
  - Headers: `X-API-Key: <API_KEY>`, `Content-Type: application/json`
  - Body: `{ "key": "={{$json.key}}" }`

### Verification (end-to-end)

1. Trigger chat → Agent calls schema tool → receives schema (non-null).
2. Keys selected → Split In Batches loops HTTP Request to `/redis/json-get`.
3. Aggregation node builds combined content → Content Agent produces final output.
4. Check Railway logs for 2xx responses and latency < 500ms.

