from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings():
    DATABASE_URL:                 str = "postgresql+asyncpg://hibou:root@localhost/grand_duc"
    SECRET_KEY:                   str = "changez_cette_cle_en_production"
    ALGORITHM:                    str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 480
    ADMIN_CORS_ORIGIN:            str = "http://localhost:5173"
    # Répertoire contenant les fichiers grand-duc-ca.crt / grand-duc-ca.key
    # Doit correspondre au répertoire de travail du proxy au démarrage.
    CERT_DIR:                     str = "D:/Bureau/grand-duc/target/debug"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
        # Force le .env à primer sur les variables système :
        case_sensitive=False,
    )

settings = Settings()