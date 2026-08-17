"""
Bot principal adaptado para Render
Inclui webhook para health check
"""
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger
from aiohttp import web
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Importar middlewares
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.middlewares.channel_middleware import ChannelMembershipMiddleware

# Importar serviços
from services.product_service import ProductService
from services.publication_service import PublicationService
from services.alert_service import AlertService

# Importar workers
from workers.scheduler_worker import SchedulerWorker
from workers.monitoring_worker import MonitoringWorker


async def health_check(request):
    """Health check para Render"""
    return web.Response(text='OK', status=200)


async def start_web_server():
    """Inicia servidor web para health check"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Web server started on port {port}")


async def main():
    """Função principal"""
    try:
        # Inicializar banco de dados
        await init_database()
        logger.info("✅ Database initialized")
        
        # Inicializar Redis (opcional)
        try:
            await init_redis()
        except:
            logger.warning("⚠️ Redis not available, continuing without it")
        
        # Configurar bot
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Configurar dispatcher
        dp = Dispatcher(storage=MemoryStorage())
        
        # Registrar middlewares
        dp.message.middleware(ChannelMembershipMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        dp.message.middleware(AuthMiddleware())
        
        # Registrar routers
        dp.include_router(admin_router)
        dp.include_router(admin_crud_router)
        dp.include_router(template_router)
        dp.include_router(category_router)
        dp.include_router(schedule_router)
        dp.include_router(button_router)
        dp.include_router(stats_router)
        dp.include_router(user_router)
        dp.include_router(callback_router)
        
        # Configurar comandos
        commands = [
            BotCommand(command="start", description="🚀 Iniciar bot"),
            BotCommand(command="help", description="❓ Ajuda"),
            BotCommand(command="offers", description="🔥 Ofertas"),
            BotCommand(command="alerts", description="🔔 Alertas"),
            BotCommand(command="categories", description="📂 Categorias"),
            BotCommand(command="admin", description="⚙️ Admin"),
        ]
        
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        
        # Iniciar workers em background
        publication_service = PublicationService()
        alert_service = AlertService()
        
        scheduler_worker = SchedulerWorker(bot, publication_service)
        monitoring_worker = MonitoringWorker(bot, alert_service)
        
        asyncio.create_task(scheduler_worker.start())
        asyncio.create_task(monitoring_worker.start())
        
        # Iniciar web server para health check
        asyncio.create_task(start_web_server())
        
        logger.info("🚀 Bot started successfully")
        
        # Iniciar polling
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member"]
        )
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    # Configurar logging
    from utils.logger import setup_logger
    setup_logger()
    
    # Executar
    asyncio.run(main())
