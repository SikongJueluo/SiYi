from pydantic_settings import BaseSettings


class AppConfiguration(BaseSettings):
    APP_NAME = "SiYi API"


config = AppConfiguration()
