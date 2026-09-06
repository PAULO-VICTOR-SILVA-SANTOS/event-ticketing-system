from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import (
    auth,
    checkin,
    dashboard,
    events,
    expenses,
    participants,
    payments,
    public_config,
)

app = FastAPI(
    title="Event Ticketing System",
    description="API para gerenciamento e venda de ingressos para eventos.",
    version="0.1.0",
)

# Local dev frontends (public ticketing page + admin panel served via
# `python -m http.server`) plus any exact custom domain set via
# EXTRA_CORS_ORIGIN. Any *.railway.app deploy preview/domain is matched
# separately below via allow_origin_regex.
CORS_ORIGINS = [
    "http://localhost:5500",
    "http://localhost:5501",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5501",
]
if settings.EXTRA_CORS_ORIGIN:
    CORS_ORIGINS.append(settings.EXTRA_CORS_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_V1_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(events.router, prefix=API_V1_PREFIX)
app.include_router(participants.router, prefix=API_V1_PREFIX)
app.include_router(expenses.router, prefix=API_V1_PREFIX)
app.include_router(dashboard.router, prefix=API_V1_PREFIX)
app.include_router(payments.router, prefix=API_V1_PREFIX)
app.include_router(checkin.router, prefix=API_V1_PREFIX)
app.include_router(public_config.router, prefix=API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
