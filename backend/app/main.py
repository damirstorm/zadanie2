from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .models import Base
from .routers import clients, jobs

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Billing Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router)
app.include_router(jobs.router)


@app.get("/health")
def health():
    return {"status": "ok"}