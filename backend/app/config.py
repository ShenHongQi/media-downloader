from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = ""
    http_timeout: int = 30
    download_proxy: str = ""
    cache_ttl: int = 3600

    class Config:
        env_file = ".env"


settings = Settings()
