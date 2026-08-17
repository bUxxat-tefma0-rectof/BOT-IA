"""
Gerenciamento de sessão do banco de dados
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from config import settings
from database.models import Base
from loguru import logger
import asyncio


class DatabaseManager:
    """Gerenciador de conexão com banco de dados"""
    
    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        self.sync_engine = None
        self.sync_session_factory = None
        
    async def initialize(self):
        """Inicializa conexões com o banco de dados"""
        try:
            # Engine assíncrono
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Factory de sessão assíncrona
            self.async_session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Engine síncrono (para alembic e tarefas síncronas)
            sync_url = settings.DATABASE_URL.replace('+asyncpg', '')
            self.sync_engine = create_engine(
                sync_url,
                echo=settings.DEBUG,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            self.sync_session_factory = sessionmaker(
                self.sync_engine,
                expire_on_commit=False
            )
            
            logger.info("✅ Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager para sessão assíncrona"""
        if not self.async_session_factory:
            await self.initialize()
        
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def get_session_no_commit(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager para sessão sem commit automático"""
        if not self.async_session_factory:
            await self.initialize()
        
        async with self.async_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()
    
    def get_sync_session(self):
        """Retorna sessão síncrona"""
        if not self.sync_session_factory:
            raise RuntimeError("Sync session factory not initialized")
        return self.sync_session_factory()
    
    async def create_tables(self):
        """Cria todas as tabelas no banco de dados"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            raise
    
    async def drop_tables(self):
        """Remove todas as tabelas do banco de dados"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("✅ Database tables dropped successfully")
        except Exception as e:
            logger.error(f"❌ Failed to drop tables: {e}")
            raise
    
    async def close(self):
        """Fecha todas as conexões"""
        try:
            if self.engine:
                await self.engine.dispose()
            if self.sync_engine:
                self.sync_engine.dispose()
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.error(f"❌ Failed to close database connections: {e}")
            raise


# Instância global do gerenciador de banco de dados
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency para FastAPI (se necessário)"""
    async with db_manager.get_session() as session:
        yield session


async def init_database():
    """Inicializa o banco de dados"""
    await db_manager.initialize()
    await db_manager.create_tables()
    logger.info("Database initialization completed")
