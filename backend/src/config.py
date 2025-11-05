from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    APP_NAME: str = "SiYi API"
    MQTT_BROKER_HOST: str = "broker.emqx.io"
    MQTT_BROKER_PORT: int = 1883
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
