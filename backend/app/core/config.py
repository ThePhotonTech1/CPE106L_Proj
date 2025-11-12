from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    jwt_secret: str = "dev"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 30
    refresh_ttl_days: int = 14
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "foodbridge"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
