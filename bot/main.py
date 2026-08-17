"""
Arquivo principal do bot
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger
from config import settings
from database.session import db_manager, init_database
from redis_manager import redis_manager, init_redis
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.callback_handlers import router as callback_router
from bot.middlewares.auth_middleware import AuthMiddleware, AdminMiddleware
from bot.middlewares.channel_middleware import ChannelMembershipMiddleware
from services.product_service import ProductService
from services.publication_service import PublicationService
from services.alert_service import AlertService
from workers.scheduler_worker import SchedulerWorker
from workers.monitoring_worker import MonitoringWorker


class TechOffersBot:
    """Classe principal do bot"""
    
    def __init__(self):
        self.bot = None
        self.dp = None
        self.storage = None
        self.scheduler_worker = None
        self.monitoring_worker = None
        
        # Serviços
        self.product_service = ProductService()
        self.publication_service = PublicationService()
        self.alert_service = AlertService()
        
    async def setup(self):
        """Configura o bot e seus componentes"""
        try:
            # Inicializar banco de dados
            await init_database()
            
            # Inicializar Redis
            await init_redis()
            
            # Configurar storage
            if redis_manager.redis_client:
                self.storage = RedisStorage(redis_manager.redis_client)
            else:
                self.storage = MemoryStorage()
            
            # Configurar bot
            self.bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Configurar dispatcher
            self.dp = Dispatcher(storage=self.storage)
            
            # Registrar middlewares
            self.dp.message.middleware(ChannelMembershipMiddleware())
            self.dp.callback_query.middleware(AuthMiddleware())
            self.dp.message.middleware(AuthMiddleware())
            
            # Registrar routers
            self.dp.include_router(admin_router)
            self.dp.include_router(user_router)
            self.dp.include_router(callback_router)
            
            # Configurar workers
            self.scheduler_worker = SchedulerWorker(self.bot, self.publication_service)
            self.monitoring_worker = MonitoringWorker(self.bot, self.alert_service)
            
            # Configurar comandos do bot
            await self.setup_commands()
            
            logger.info("✅ Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Bot setup failed: {e}")
            raise
    
    async def setup_commands(self):
        """Configura os comandos do bot"""
        commands = [
            BotCommand(command="start", description="🚀 Iniciar bot"),
            BotCommand(command="help", description="❓ Ajuda e suporte"),
            BotCommand(command="offers", description="🔥 Ver ofertas ativas"),
            BotCommand(command="alerts", description="🔔 Meus alertas"),
            BotCommand(command="categories", description="📂 Categorias"),
            BotCommand(command="admin", description="⚙️ Painel administrativo"),
        ]
        
        await self.bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeDefault()
        )
        
        logger.info("✅ Bot commands configured")
    
    async def start(self):
        """Inicia o bot e workers"""
        try:
            await self.setup()
            
            # Iniciar workers
            if self.scheduler_worker:
                await self.scheduler_worker.start()
            
            if self.monitoring_worker:
                await self.monitoring_worker.start()
            
            logger.info("🚀 Bot started successfully")
            
            # Iniciar polling
            await self.dp.start_polling(
                self.bot,
                allowed_updates=["message", "callback_query", "chat_member"]
            )
            
        except Exception as e:
            logger.error(f"❌ Bot failed to start: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Para o bot e limpa recursos"""
        try:
            if self.scheduler_worker:
                await self.scheduler_worker.stop()
            
            if self.monitoring_worker:
                await self.monitoring_worker.stop()
            
            if self.bot:
                await self.bot.session.close()
            
            await db_manager.close()
            await redis_manager.close()
            
            logger.info("👋 Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")


async def main():
    """Função principal"""
    bot_app = TechOffersBot()
    
    try:
        await bot_app.start()
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    # Configurar logging
    logger.add(
        f"{settings.LOGS_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log",
        rotation="500 MB",
        retention="30 days",
        level=settings.LOG_LEVEL
    )
    
    # Executar bot
    asyncio.run(main())
