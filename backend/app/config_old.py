from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "foodbridge"
    API_PREFIX: str = "/api"

    class Config:
        env_file = ".env"

settings = Settings()
