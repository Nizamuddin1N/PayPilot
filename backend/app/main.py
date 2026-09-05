from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import ALLOWED_ORIGINS
from app.database import Base, engine
from app.routers import agent, audit, catalog, orders, webhooks

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agentic Commerce — Track 01 (Phase 1: catalog + payments, no AI)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(webhooks.router)
app.include_router(agent.router)
app.include_router(audit.router)

app.mount("/test", StaticFiles(directory="static", html=True), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}
