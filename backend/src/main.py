import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from starlette import status
from backend.src.config import get_app_settings
from backend.src.logger_setup import logger_setup

logger_setup()
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Init
    yield
    # Close


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


@app.get("/", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def root():
    logger.info("Redict to frontend...")
    return RedirectResponse("http://localhost:3000", status.HTTP_308_PERMANENT_REDIRECT)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await logger.ainfo(
        "Connect to web socket: %{socket}", {"socket": websocket.client.host}
    )

    while True:
        data = await websocket.receive_text()
        await logger.ainfo("Receive Message: %{data}", {"data": data})
