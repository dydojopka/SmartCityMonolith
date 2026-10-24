import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.errors import validation_error
from app.init_db import init_database

SERVICE_NAME = os.getenv("SERVICE_NAME", "smart-city-monolith")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    logger.info("%s started (infrastructure; module routers are not connected yet)", SERVICE_NAME)
    yield


app = FastAPI(title="Smart City Modular Monolith", lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# После принятия модулей: импорт router из каждого модуля и app.include_router(router).
# Префиксы /api, /utility и /notification не добавляются.


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
