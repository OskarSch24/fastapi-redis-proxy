import json
import os
from typing import List, Optional

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid


app = FastAPI(title="FastAPI Redis Proxy", version="0.1.0")


class JsonGetRequest(BaseModel):
    key: str


class CommandRequest(BaseModel):
    command: str
    args: List[str] = []


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server API key not configured")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def create_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST")
    port_str = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD")
    use_tls = os.getenv("REDIS_TLS", "false").lower() in ("1", "true", "yes")

    if not host or not password:
        raise RuntimeError("Missing REDIS_HOST or REDIS_PASSWORD environment variables")

    port = int(port_str)
    return redis.Redis(host=host, port=port, password=password, ssl=use_tls, decode_responses=True)


redis_client: Optional[redis.Redis] = None


@app.on_event("startup")
def on_startup() -> None:
    global redis_client
    redis_client = create_redis_client()
    # Simple ping to validate connectivity
    try:
        redis_client.ping()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to connect to Redis: {exc}")


@app.on_event("shutdown")
def on_shutdown() -> None:
    global redis_client
    if redis_client is not None:
        try:
            redis_client.close()
        finally:
            redis_client = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _parse_maybe_json_string(value: Optional[str]):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


ALLOWED_COMMANDS = {"JSON.GET"}
ALLOWED_KEY_PREFIXES = ("doc:", "ch:", "index:")
MAX_KEY_LEN = 256
MAX_ARGS_LEN = 10


@app.post("/redis/json-get")
def json_get(req: JsonGetRequest, _auth: None = Depends(require_api_key)) -> dict:
    if not req.key or not req.key.startswith(ALLOWED_KEY_PREFIXES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Key prefix not allowed")
    if len(req.key) > MAX_KEY_LEN:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Key too long")

    assert redis_client is not None, "Redis client not initialized"
    try:
        result = redis_client.execute_command("JSON.GET", req.key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Redis error: {exc}")

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    return {"result": _parse_maybe_json_string(result)}


@app.post("/redis/command")
def command(req: CommandRequest, _auth: None = Depends(require_api_key)) -> dict:
    command_upper = (req.command or "").upper()
    if command_upper not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Command not allowed")

    # Optional: basic guard for args (e.g., enforce key prefix on first arg)
    if len(req.args) > MAX_ARGS_LEN:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too many arguments")
    if req.args:
        first = req.args[0]
        if isinstance(first, str) and not first.startswith(ALLOWED_KEY_PREFIXES):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Key prefix not allowed")

    assert redis_client is not None, "Redis client not initialized"
    try:
        result = redis_client.execute_command(command_upper, *req.args)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Redis error: {exc}")

    return {"result": _parse_maybe_json_string(result)}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.time()
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        try:
            response = await call_next(request)
            duration_ms = int((time.time() - started) * 1000)
            print(
                json.dumps(
                    {
                        "event": "request",
                        "requestId": req_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "durationMs": duration_ms,
                    }
                )
            )
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            duration_ms = int((time.time() - started) * 1000)
            print(
                json.dumps(
                    {
                        "event": "error",
                        "requestId": req_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(exc),
                        "durationMs": duration_ms,
                    }
                )
            )
            raise


app.add_middleware(RequestLoggingMiddleware)

