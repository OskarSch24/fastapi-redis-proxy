# FastAPI Redis Proxy

A secure HTTP proxy service that provides authenticated access to Redis Cloud (RedisJSON) for n8n workflow automation. This service acts as a middleware layer between n8n and Redis Cloud, handling authentication, validation, and secure TLS connections.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Security Model](#security-model)
- [Deployment](#deployment)
- [Development](#development)
- [n8n Integration](#n8n-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

This FastAPI service solves several key challenges:

1. **Security Layer**: Provides API key authentication for Redis access from n8n workflows
2. **TLS Handling**: Manages complex TLS connections to Redis Cloud with automatic fallback
3. **Validation**: Enforces key prefix restrictions and command whitelisting
4. **Simplified Interface**: Exposes clean HTTP endpoints instead of direct Redis protocol

### Use Case

Designed for AI-powered content generation workflows where:
- n8n workflows need to query Redis for brand guidelines, content templates, and documentation
- AI agents dynamically select relevant data based on user requests
- Security and access control are critical

---

## Architecture

```
┌─────────┐                    ┌──────────────────┐                    ┌─────────────┐
│   n8n   │ ──── HTTPS ────────▶│  FastAPI Proxy   │ ──── TLS ─────────▶│ Redis Cloud │
│Workflow │    (API Key Auth)   │   (Railway)      │  (Validated)       │  (RedisJSON)│
└─────────┘                    └──────────────────┘                    └─────────────┘
                                        │
                                        ├─ Authentication (X-API-Key)
                                        ├─ Key Prefix Validation
                                        ├─ Command Whitelisting
                                        └─ TLS Connection Management
```

### Technology Stack

- **Framework**: FastAPI (Python)
- **Redis Client**: redis-py with RedisJSON support
- **Deployment**: Railway (auto-deploy from GitHub)
- **Database**: Redis Cloud with TLS
- **Protocol**: HTTP/HTTPS with JSON payloads

### Data Flow

1. n8n sends HTTP POST with API key header
2. FastAPI validates API key and request format
3. FastAPI validates key prefixes and commands
4. FastAPI executes Redis JSON command over TLS
5. Response is formatted and returned to n8n

---

## API Endpoints

### 1. `/redis/json-get` - Single Key Retrieval

Retrieve a single key from Redis with validation.

**Method**: `POST`

**Headers**:
```http
X-API-Key: your_api_key_here
Content-Type: application/json
```

**Request Body**:
```json
{
  "key": "doc:brand_brief:001"
}
```

**Response** (200 OK):
```json
{
  "result": {
    "title": "Brand Brief",
    "content": "..."
  }
}
```

**Errors**:
- `400`: Key prefix not allowed or key too long (>256 chars)
- `401`: Invalid or missing API key
- `404`: Key not found
- `502`: Redis connection error

---

### 2. `/redis/command` - Whitelisted JSON Commands

Execute specific Redis JSON commands with arguments.

**Method**: `POST`

**Headers**:
```http
X-API-Key: your_api_key_here
Content-Type: application/json
```

**Request Body**:
```json
{
  "command": "JSON.GET",
  "args": ["index:database_schema"]
}
```

**Allowed Commands**:
- `JSON.GET` - Retrieve JSON data

**Response** (200 OK):
```json
{
  "result": {
    "documents": [...],
    "chapters": [...]
  }
}
```

**Errors**:
- `400`: Command not allowed or key prefix invalid
- `401`: Invalid or missing API key
- `413`: Too many arguments (>10)
- `502`: Redis connection error

---

### 3. `/redis/query` - Universal Flexible Endpoint

Universal endpoint supporting multiple query formats for maximum flexibility.

**Method**: `POST`

**Headers**:
```http
X-API-Key: your_api_key_here
Content-Type: application/json
```

#### Format 1: Single Key with JSON Path

```json
{
  "key": "doc:brand_brief:001",
  "path": "."
}
```

#### Format 2: Direct JSON Command

```json
{
  "command": "JSON.GET",
  "args": ["index:main", ".documents"]
}
```

#### Format 3: Multiple Keys (Batch Retrieval)

```json
{
  "keys": [
    "doc:brand_brief:001",
    "ch:marketing:005",
    "index:main"
  ]
}
```

**Response for Multiple Keys**:
```json
{
  "results": {
    "doc:brand_brief:001": {...},
    "ch:marketing:005": {...},
    "index:main": {...}
  }
}
```

**Validation**:
- Only `JSON.*` commands allowed
- All keys must start with allowed prefixes
- Maximum 10 arguments per command
- Keys returning null are included in results as `null`

---

### 4. `/health` - Health Check

Simple health check endpoint for monitoring.

**Method**: `GET`

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

---

## Security Model

### Authentication

**API Key Header**: All endpoints (except `/health`) require the `X-API-Key` header.

```python
X-API-Key: n8n_railway_auth_k9mP2xL7vQ4wN8jR5tY6uE3sA1bC0dF
```

The API key is validated against the `API_KEY` environment variable. Requests without a valid key receive `401 Unauthorized`.

### Key Prefix Validation

Only keys with specific prefixes are allowed to prevent unauthorized data access:

- `doc:` - Documents (e.g., `doc:brand_brief:001`)
- `ch:` - Chapters (e.g., `ch:marketing:005`)
- `index:` - Index keys (e.g., `index:database_schema`)
- `p:` - Paragraphs (e.g., `p:brand_identity:001`)
- `para:` - Paragraphs (alternative format)
- `sp:` - Subparagraphs (e.g., `sp:values:002`)
- `ssp:` - Sub-subparagraphs (e.g., `ssp:details:003`)
- `chunk:` - Text chunks (e.g., `chunk:content:001`)

**Example**:
- ✅ `doc:brand_brief:001` - Allowed
- ✅ `ch:marketing:005` - Allowed
- ✅ `p:brand_identity:001` - Allowed
- ✅ `chunk:content:042` - Allowed
- ✅ `index:main` - Allowed
- ❌ `user:passwords:admin` - Rejected (400)
- ❌ `config:api_keys` - Rejected (400)

### Command Whitelisting

Only safe, read-only JSON commands are allowed:

**Allowed**:
- `JSON.GET` - Read JSON data
- `JSON.*` commands (in `/redis/query` endpoint)

**Blocked**:
- `JSON.SET` - Write operations
- `JSON.DEL` - Delete operations
- `FLUSHDB` - Dangerous commands
- Standard Redis commands without JSON prefix

### Additional Protections

- **Max Key Length**: 256 characters
- **Max Arguments**: 10 per command
- **TLS Required**: All Redis connections use TLS
- **Request Logging**: All requests logged with duration and status

---

## Deployment

### Railway Deployment

This service is designed for Railway auto-deployment from GitHub.

#### Setup Steps

1. **Create Railway Project**:
   - New Project → Deploy from GitHub
   - Select repository: `OskarSch24/fastapi-redis-proxy`
   - Root directory: `/`

2. **Configure Start Command**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. **Set Environment Variables**:
   ```bash
   REDIS_HOST=redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com
   REDIS_PORT=13515
   REDIS_PASSWORD=your_redis_cloud_password
   REDIS_TLS=true
   API_KEY=n8n_railway_auth_k9mP2xL7vQ4wN8jR5tY6uE3sA1bC0dF
   PYTHONUNBUFFERED=1
   ```

4. **Health Check**:
   - Endpoint: `/health`
   - Expected: `{"status": "ok"}`

#### Auto-Deployment

Railway automatically deploys on every push to `main` branch:
- Build time: ~2 minutes
- Zero-downtime deployment
- Automatic HTTPS certificate

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `REDIS_HOST` | Yes | Redis Cloud hostname | `redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com` |
| `REDIS_PORT` | Yes | Redis Cloud port | `13515` |
| `REDIS_PASSWORD` | Yes | Redis Cloud password | `your_password_here` |
| `REDIS_TLS` | Yes | Enable TLS connection | `true` |
| `API_KEY` | Yes | API key for n8n authentication | `n8n_railway_auth_...` |
| `PYTHONUNBUFFERED` | No | Disable Python output buffering | `1` |

---

## Development

### Local Setup

1. **Clone Repository**:
   ```bash
   git clone https://github.com/OskarSch24/fastapi-redis-proxy.git
   cd fastapi-redis-proxy
   ```

2. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Environment Variables**:
   ```bash
   export REDIS_HOST=your_redis_host
   export REDIS_PORT=13515
   export REDIS_PASSWORD=your_password
   export REDIS_TLS=true
   export API_KEY=test_api_key_123
   ```

5. **Run Server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```

6. **Test Health Endpoint**:
   ```bash
   curl http://localhost:8080/health
   ```

### Testing Endpoints

**Test `/redis/json-get`**:
```bash
curl -X POST http://localhost:8080/redis/json-get \
  -H "X-API-Key: test_api_key_123" \
  -H "Content-Type: application/json" \
  -d '{"key": "doc:brand_brief:001"}'
```

**Test `/redis/query`**:
```bash
curl -X POST http://localhost:8080/redis/query \
  -H "X-API-Key: test_api_key_123" \
  -H "Content-Type: application/json" \
  -d '{"command": "JSON.GET", "args": ["index:main"]}'
```

### Dependencies

See [`requirements.txt`](requirements.txt):
```
fastapi
uvicorn[standard]
redis
pydantic
```

---

## n8n Integration

### Workflow Architecture

```
Chat Trigger
    ↓
Query Reasoning Agent (AI)
    ├─→ Calls "Get Database Schema Tool" (HTTP Request to /redis/query)
    ↓   Returns: List of available keys
    ↓
    Output: Selected keys for content generation
    ↓
Parse Queries → Split In Batches
    ↓
HTTP Request Node (Loop)
    ├─→ POST /redis/json-get for each key
    ↓
Aggregate Results
    ↓
Content Generation Agent (AI)
```

### Example: Get Database Schema Tool

**Node Type**: `@n8n/n8n-nodes-langchain.toolHttpRequest`

**Configuration**:
- **Method**: POST
- **URL**: `https://fastapi-redis-proxy-production.up.railway.app/redis/query`
- **Headers**:
  ```json
  {
    "Content-Type": "application/json",
    "X-API-Key": "n8n_railway_auth_k9mP2xL7vQ4wN8jR5tY6uE3sA1bC0dF"
  }
  ```
- **Body**:
  ```json
  {
    "command": "JSON.GET",
    "args": ["index:database_schema"]
  }
  ```

### Example: Fetch Content Loop

**Node Type**: `n8n-nodes-base.httpRequest`

**Configuration**:
- **Method**: POST
- **URL**: `https://fastapi-redis-proxy-production.up.railway.app/redis/json-get`
- **Headers**:
  ```json
  {
    "Content-Type": "application/json",
    "X-API-Key": "n8n_railway_auth_k9mP2xL7vQ4wN8jR5tY6uE3sA1bC0dF"
  }
  ```
- **Body**:
  ```json
  {
    "key": "{{ $json.key }}"
  }
  ```

### Verification Steps

1. **Trigger Workflow**: Send test message via Chat Trigger
2. **Check Schema Tool**: Verify AI agent receives non-null schema
3. **Check Key Selection**: Verify AI selects valid keys from schema
4. **Check Data Retrieval**: Verify HTTP Request loop fetches actual data
5. **Check Railway Logs**: Verify 200 responses and latency <500ms

---

## Troubleshooting

### Common Errors

#### HTTP 401 Unauthorized

**Cause**: Missing or invalid API key

**Solution**:
1. Check `X-API-Key` header is present in request
2. Verify API key matches `API_KEY` environment variable in Railway
3. Ensure no extra spaces or quotes in the key

**n8n Fix**:
```json
{
  "headers": {
    "X-API-Key": "n8n_railway_auth_k9mP2xL7vQ4wN8jR5tY6uE3sA1bC0dF"
  }
}
```

---

#### HTTP 400 Bad Request

**Cause**: Invalid key prefix or malformed request body

**Common Issues**:
- Key doesn't start with `doc:`, `ch:`, or `index:`
- Empty or missing `key` field in body
- Invalid JSON format

**Solution**:
```json
// ❌ Wrong
{"key": "user:data:001"}

// ✅ Correct
{"key": "doc:brand_brief:001"}
```

---

#### HTTP 422 Unprocessable Entity

**Cause**: Request body doesn't match expected schema

**Common Issues**:
- `/redis/command` expects `{"command": "...", "args": [...]}`
- `/redis/json-get` expects `{"key": "..."}`
- Wrong endpoint for the request format

**Solution**: Match body format to endpoint requirements (see [API Endpoints](#api-endpoints))

---

#### HTTP 404 Not Found

**Cause**: Key doesn't exist in Redis

**Solution**:
1. Verify key name is correct (check spelling, case-sensitivity)
2. Use `/redis/query` with `{"command": "JSON.GET", "args": ["index:database_schema"]}` to see available keys
3. Ensure data was uploaded to Redis

---

#### HTTP 502 Bad Gateway

**Cause**: Redis connection failed

**Possible Reasons**:
- Redis Cloud is down
- TLS certificate issue
- Network connectivity problem
- Invalid Redis credentials

**Solution**:
1. Check Railway logs for detailed error message
2. Verify `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` in Railway environment variables
3. Test Redis connection directly using redis-cli
4. Check Redis Cloud dashboard for service status

---

### Debugging Tips

1. **Check Railway Logs**:
   - Railway Dashboard → Service → Logs
   - Look for request/error events with request IDs
   - Check duration and status codes

2. **Test Locally**:
   - Run server locally with same environment variables
   - Use curl or Postman to test endpoints
   - Check detailed error messages in terminal

3. **Verify n8n Configuration**:
   - Ensure headers are set as JSON, not key-value pairs
   - Check for expression syntax errors (`{{ }}`)
   - Test node execution individually

4. **Redis Connection**:
   - Test with redis-cli: `redis-cli -h <host> -p <port> --tls -a <password>`
   - Verify TLS is enabled in Railway environment
   - Check fallback behavior in logs

---

### Debug Reports

Detailed debugging sessions and setup guides are available in the [`reports/`](reports/) directory:

- [`n8n_HTTP_Request_Debug_Session.md`](reports/n8n_HTTP_Request_Debug_Session.md) - Complete debugging session for HTTP 422/400 errors
- [`WORKFLOW_FIX_SUMMARY.md`](reports/WORKFLOW_FIX_SUMMARY.md) - Null query problem and schema loading solution
- [`Server_Configuration_Education_Plan_Discussion.md`](reports/Server_Configuration_Education_Plan_Discussion.md) - Server configuration concepts
- [`MCP_Redis_HTTPS_Setup_Report.md`](reports/MCP_Redis_HTTPS_Setup_Report.md) - Original HTTPS server setup

---

## License

MIT

## Repository

https://github.com/OskarSch24/fastapi-redis-proxy
