"""
Configurações globais do sistema
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Configurações principais do sistema"""
    
    # Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/tech_offers")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    
    # API Keys
    SHOPEE_API_KEY: Optional[str] = os.getenv("SHOPEE_API_KEY", None)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    
    # System Paths
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    BACKUP_DIR: str = os.path.join(BASE_DIR, "backups")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Criar diretórios necessários
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)
