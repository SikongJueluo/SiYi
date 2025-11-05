import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette import status
from backend.src.config import get_app_settings
from backend.src.mqtt.router import close_mqtt, init_mqtt, router as mqtt_router

# StructLog config
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # structlog.processors.JSONRenderer(),  # 生产环境用 JSON
        structlog.dev.set_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),  # 开发环境用这个
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Init
    await init_mqtt()
    yield
    # Close
    await close_mqtt()


description = """
Web-based Minecraft server management tool using RCON protocol or MCDR, built with fastapi and solidjs. 
"""


app = FastAPI(
    title=get_app_settings().APP_NAME,
    description=description,
    summary="Web-based Minecraft server management tool.",
    version="0.1.0",
    # terms_of_service="http://example.com/terms/",
    contact={
        "name": "SikongJueluo",
        "url": "https://github.com/SikongJueluo",
        "email": "selfconfusion@gmail.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/license/mit",
    },
    lifespan=lifespan,
)

app.include_router(mqtt_router)


@app.get("/", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def root():
    logger.info("Redict to frontend...")
    return RedirectResponse("http://localhost:3000", status.HTTP_308_PERMANENT_REDIRECT)
