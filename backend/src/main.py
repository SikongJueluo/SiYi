from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette import status
from src.mqtt.router import router as mqtt_router
from src.config import config

description = """
Web-based Minecraft server management tool using RCON protocol or MCDR, built with fastapi and solidjs. 
"""

app = FastAPI(
    title=config.APP_NAME,
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
)
app.include_router(mqtt_router)


@app.get("/", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def root():
    return RedirectResponse("http://localhost:3000", status.HTTP_308_PERMANENT_REDIRECT)
