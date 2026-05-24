from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import db
from .adapters.gemini import get_status as get_gemini_status
from .adapters.openai import get_status as get_llm_status
from .auth import ensure_admin_from_env
from .config import PROJECT_ROOT
from .deps import require_auth
from .pipeline.errors import error_payload
from .pipeline.logging import configure_analysis_logging, console_error, new_request_id
from .routers.analyze_router import router as analyze_router
from .routers.auth_router import router as auth_router
from .routers.firecrawl_router import router as firecrawl_router
from .routers.user_router import router as user_router


logger = logging.getLogger(__name__)
_DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_analysis_logging()
    db.init_db()
    ensure_admin_from_env()
    yield


app = FastAPI(
    title="Fintech Trendwatcher API",
    lifespan=lifespan,
    docs_url="/docs" if _DEBUG else None,
    redoc_url="/redoc" if _DEBUG else None,
    openapi_url="/openapi.json" if _DEBUG else None,
)

_DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]
_extra_origins = [o.strip() for o in os.environ.get("FRONTEND_URL", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=(_DEFAULT_DEV_ORIGINS if _DEBUG else []) + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(analyze_router)
app.include_router(firecrawl_router)


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or new_request_id()
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = _get_request_id(request)
    detail = exc.detail
    if isinstance(detail, dict):
        payload = {**detail}
        payload.setdefault("ok", False)
        payload.setdefault("error", "API_ERROR")
        payload.setdefault("message", "")
        payload.setdefault("request_id", rid)
        return JSONResponse(status_code=exc.status_code, content={"detail": payload},
                            headers={"X-Request-Id": rid})
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": error_payload(
            "API_ERROR",
            detail if isinstance(detail, str) else "",
            request_id=rid,
        )},
        headers={"X-Request-Id": rid},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = _get_request_id(request)
    return JSONResponse(
        status_code=422,
        content={"detail": error_payload(
            "VALIDATION_ERROR",
            "Request payload did not match the expected schema.",
            request_id=rid,
            details={"errors": exc.errors()[:5]},
        )},
        headers={"X-Request-Id": rid},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = _get_request_id(request)
    console_error(rid, "response", exc, route=request.url.path)
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": error_payload(
            "UNKNOWN_ERROR", f"{type(exc).__name__}: {exc}", request_id=rid,
        )},
        headers={"X-Request-Id": rid},
    )


def _get_request_id(request: Request) -> str:
    rid = getattr(getattr(request, "state", None), "request_id", None)
    return rid or new_request_id()


@app.get("/")
def root():
    if FRONTEND_DIST_DIR.exists():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
    return {"name": "Fintech Trendwatcher API", "status": "ok", "health": "/api/health"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/llm-status")
def llm_status(user: dict = Depends(require_auth)):
    return {"openai": get_llm_status(), "gemini": get_gemini_status()}


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):
    if not FRONTEND_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    asset_path = (FRONTEND_DIST_DIR / full_path).resolve()
    if asset_path.is_file() and _inside_frontend_dist(asset_path):
        return FileResponse(asset_path)
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


def _inside_frontend_dist(path: Path) -> bool:
    try:
        path.relative_to(FRONTEND_DIST_DIR.resolve())
        return True
    except ValueError:
        return False
