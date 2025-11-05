from fastapi import APIRouter
from fastapi_mqtt import FastMQTT, MQTTConfig
import gmqtt
import structlog

from backend.src.config import get_app_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

mqtt = FastMQTT(
    config=MQTTConfig(
        host=get_app_settings().MQTT_BROKER_HOST,
        port=get_app_settings().MQTT_BROKER_PORT,
    )
)

router = APIRouter(
    prefix="/mqtt",
    tags=["MQTT"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


async def init_mqtt():
    await mqtt.mqtt_startup()


async def close_mqtt():
    await mqtt.mqtt_shutdown()


@mqtt.on_connect()
def connect(client: gmqtt.Client, flags, rc, properties):
    mqtt.client.subscribe("/mqtt")  # subscribing mqtt topic
    logger.info("Connected", flags=flags, rc=rc, properties=properties)


@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    logger.info("Received message: ", topic, payload.decode(), qos, properties)
    return 0


@mqtt.subscribe("my/mqtt/topic/#")
async def message_to_topic(client, topic, payload, qos, properties):
    logger.info(
        "Received message to specific topic: ", topic, payload.decode(), qos, properties
    )


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    logger.info("Disconnected")


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    logger.info("Subscribed", mid=mid, qos=qos, properties=properties)
