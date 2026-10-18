import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()

# Your assignment's allowed origins.
ALLOWED_ORIGINS = [
    "https://app-2nn2qt.example.com",
    "https://exam.sanand.workers.dev",
]

# Your logged-in email will be configured on Render.
EMAIL = os.getenv("EMAIL", "24f2008896@ds.study.iitm.ac.in")

# Rate limit: 14 requests per client in 10 seconds.
RATE_LIMIT = 14
WINDOW_SECONDS = 10

client_requests = defaultdict(deque)


# Middleware 1: Request ID context.
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response


# Middleware 2: Per-client rate limiter.
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Let CORS preflight requests reach the CORS middleware.
        if request.method == "OPTIONS":
            return await call_next(request)

        client_id = request.headers.get("X-Client-Id")

        if not client_id:
            client_id = request.client.host if request.client else "unknown"

        now = time.monotonic()
        timestamps = client_requests[client_id]

        # Remove requests outside the 10-second window.
        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()

        # Reject the 15th request and later requests in the window.
        if len(timestamps) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        timestamps.append(now)
        return await call_next(request)


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }

app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)
