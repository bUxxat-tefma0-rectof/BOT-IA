"""
Configuração de logging do sistema
"""
import sys
import logging
from loguru import logger
from pathlib import Path
from datetime import datetime
from typing import Optional
from config import settings


class InterceptHandler(logging.Handler):
    """Handler para interceptar logs do Python e redirecionar para Loguru"""
    
    def emit(self, record):
        # Obter correspondente Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # Encontrar caller
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger(log_level: Optional[str] = None):
    """
    Configura o sistema de logging
    
    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    try:
        # Remover handlers padrão
        logger.remove()
        
        # Definir nível de log
        level = log_level or settings.LOG_LEVEL
        
        # Log para console
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
        # Log para arquivo
        log_file = Path(settings.LOGS_DIR) / f"tech_offers_{datetime.now().strftime('%Y%m%d')}.log"
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation="500 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )
        
        # Log para erros em arquivo separado
        error_file = Path(settings.LOGS_DIR) / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        logger.add(
            error_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )
        
        # Configurar logging padrão do Python
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
        
        # Configurar loggers de bibliotecas
        for logger_name in ['aiogram', 'sqlalchemy', 'apscheduler', 'aiohttp']:
            logging_logger = logging.getLogger(logger_name)
            logging_logger.handlers = [InterceptHandler()]
            logging_logger.propagate = False
        
        logger.info(f"Logger configured with level: {level}")
        logger.info(f"Log files directory: {settings.LOGS_DIR}")
        
        return logger
        
    except Exception as e:
        print(f"Error setting up logger: {e}")
        return logger


def get_logger(name: str = None):
    """
    Obtém logger configurado
    
    Args:
        name: Nome do logger (opcional)
    
    Returns:
        Logger configurado
    """
    if name:
        return logger.bind(name=name)
    return logger


class LoggerMixin:
    """Mixin para adicionar logger a classes"""
    
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
