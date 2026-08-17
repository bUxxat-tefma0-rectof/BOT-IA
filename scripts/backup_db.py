"""
Script para backup do banco de dados
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import shutil

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from loguru import logger


async def backup_database():
    """Executa backup do banco de dados"""
    try:
        logger.info("Starting database backup...")
        
        # Criar diretório de backup
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(exist_ok=True)
        
        # Nome do arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.sql"
        
        # Executar pg_dump
        import subprocess
        
        # Extrair informações da URL do banco
        db_url = settings.DATABASE_URL
        
        # Parse da URL
        # postgresql+asyncpg://user:password@localhost:5432/tech_offers
        url_parts = db_url.replace("postgresql+asyncpg://", "").split("@")
        credentials = url_parts[0].split(":")
        host_parts = url_parts[1].split("/")
        host_port = host_parts[0].split(":")
        
        user = credentials[0]
        password = credentials[1] if len(credentials) > 1 else ""
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        database = host_parts[1] if len(host_parts) > 1 else "tech_offers"
        
        # Comando pg_dump
        command = [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", database,
            "-f", str(backup_file)
        ]
        
        # Executar com senha
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Backup created: {backup_file}")
            
            # Comprimir
            shutil.make_archive(str(backup_file), 'gztar', backup_dir)
            logger.info(f"✅ Backup compressed")
            
            # Remover arquivos antigos (30 dias)
            cleanup_old_backups(backup_dir)
            
        else:
            logger.error(f"❌ Backup failed: {result.stderr}")
        
    except Exception as e:
        logger.error(f"❌ Backup error: {e}")
        raise


def cleanup_old_backups(backup_dir: Path, days: int = 30):
    """Remove backups antigos"""
    try:
        current_time = datetime.now()
        
        for file in backup_dir.glob("backup_*.sql*"):
            file_time = datetime.fromtimestamp(file.stat().st_mtime)
            
            if (current_time - file_time).days > days:
                file.unlink()
                logger.info(f"Removed old backup: {file.name}")
                
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {e}")


if __name__ == "__main__":
    asyncio.run(backup_database())
