"""
Bot principal COM sistema de suporte
"""
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger

from config import settings
from database.session import db_manager, init_database
from redis_manager import redis_manager, init_redis

# Importar handlers
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.callback_handlers import router as callback_router
from bot.handlers.admin_crud_handlers import router as admin_crud_router
from bot.handlers.template_handlers import router as template_router
from bot.handlers.category_handlers import router as category_router
from bot.handlers.schedule_handlers import router as schedule_router
from bot.handlers.button_config_handlers import router as button_router
from bot.handlers.stats_handlers import router as stats_router
from bot.handlers.support_handlers import router as support_router  # NOVO

# Importar middlewares
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.middlewares.channel_middleware import ChannelMembershipMiddleware

# Importar serviços
from services.product_service import ProductService
from services.publication_service import PublicationService
from services.alert_service import AlertService
from services.support_service import SupportService  # NOVO

# Importar workers
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
        self.support_service = SupportService()  # NOVO
        
    async def setup(self):
        """Configura o bot"""
        try:
            await init_database()
            await init_redis()
            
            if redis_manager.redis_client:
                self.storage = RedisStorage(redis_manager.redis_client)
            else:
                self.storage = MemoryStorage()
            
            self.bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            self.dp = Dispatcher(storage=self.storage)
            
            # Middlewares
            self.dp.message.middleware(ChannelMembershipMiddleware())
            self.dp.callback_query.middleware(AuthMiddleware())
            self.dp.message.middleware(AuthMiddleware())
            
            # Routers (incluindo suporte)
            self.dp.include_router(admin_router)
            self.dp.include_router(admin_crud_router)
            self.dp.include_router(template_router)
            self.dp.include_router(category_router)
            self.dp.include_router(schedule_router)
            self.dp.include_router(button_router)
            self.dp.include_router(stats_router)
            self.dp.include_router(support_router)  # NOVO
            self.dp.include_router(user_router)
            self.dp.include_router(callback_router)
            
            # Workers
            self.scheduler_worker = SchedulerWorker(self.bot, self.publication_service)
            self.monitoring_worker = MonitoringWorker(self.bot, self.alert_service)
            
            await self.setup_commands()
            
            logger.info("✅ Bot setup completed with support system")
            
        except Exception as e:
            logger.error(f"❌ Bot setup failed: {e}")
            raise
    
    async def setup_commands(self):
        """Configura comandos"""
        commands = [
            BotCommand(command="start", description="🚀 Iniciar bot"),
            BotCommand(command="help", description="❓ Ajuda"),
            BotCommand(command="offers", description="🔥 Ofertas"),
            BotCommand(command="alerts", description="🔔 Alertas"),
            BotCommand(command="categories", description="📂 Categorias"),
            BotCommand(command="support", description="💬 Suporte"),  # NOVO
            BotCommand(command="admin", description="⚙️ Admin"),
        ]
        
        await self.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    
    async def start(self):
        """Inicia o bot"""
        try:
            await self.setup()
            
            if self.scheduler_worker:
                asyncio.create_task(self.scheduler_worker.start())
            
            if self.monitoring_worker:
                asyncio.create_task(self.monitoring_worker.start())
            
            logger.info("🚀 Bot started successfully")
            
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
        """Para o bot"""
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
    from utils.logger import setup_logger
    setup_logger()
    
    asyncio.run(main())
