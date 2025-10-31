from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.models import Base
from app.routers.admin_members import router as admin_members_router
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.routers.books import router as books_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI Powered Library API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello FastAPI"}


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(books_router)
app.include_router(admin_members_router)
