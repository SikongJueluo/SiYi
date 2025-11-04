from fastapi import APIRouter


router = APIRouter(
    prefix="/mqtt",
    tags=["MQTT"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)
