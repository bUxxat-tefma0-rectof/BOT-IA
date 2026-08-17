"""
Configurações para deploy no Render
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Configurações do sistema para Render"""
    
    # Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Corrigir URL do banco para SQLAlchemy async
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Corrigir URL do Redis para Render
    if REDIS_URL and REDIS_URL.startswith("redis://"):
        # Render fornece redis:// com senha
        pass  # Já está no formato correto
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    
    # API Keys
    SHOPEE_API_KEY: str = os.getenv("SHOPEE_API_KEY", "")
    SHOPEE_PARTNER_ID: str = os.getenv("SHOPEE_PARTNER_ID", "")
    SHOPEE_SHOP_ID: str = os.getenv("SHOPEE_SHOP_ID", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # System Paths
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    BACKUP_DIR: str = os.path.join(BASE_DIR, "backups")
    
    # Port para web server
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()

# Criar diretórios necessários
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)
