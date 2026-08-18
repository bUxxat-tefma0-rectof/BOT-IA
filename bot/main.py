"""
Arquivo principal do bot - VERSÃO CORRIGIDA
Com registro correto de handlers e sistema completo
"""
import asyncio
import logging
from datetime import datetime
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

# Importar TODOS os handlers
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.callback_handlers import router as callback_router
from bot.handlers.promotion_handlers import router as promotion_router
from bot.handlers.button_handlers import router as button_router

# Importar middlewares
from bot.middlewares.auth_middleware import AuthMiddleware, AdminMiddleware
from bot.middlewares.channel_middleware import ChannelMembershipMiddleware

# Importar serviços
from services.product_service import ProductService
from services.publication_service import PublicationService
from services.alert_service import AlertService
from services.monitoring_service import MonitoringService

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
        self.monitoring_service = MonitoringService()
        
        # Flag para verificar se bot está rodando
        self.is_running = False
        
    async def setup(self):
        """Configura o bot e seus componentes"""
        try:
            logger.info("🚀 Iniciando configuração do bot...")
            
            # Inicializar banco de dados
            await init_database()
            logger.info("✅ Banco de dados inicializado")
            
            # Inicializar Redis
            await init_redis()
            logger.info("✅ Redis inicializado")
            
            # Configurar storage
            if redis_manager.redis_client:
                self.storage = RedisStorage(redis_manager.redis_client)
                logger.info("✅ Usando Redis Storage")
            else:
                self.storage = MemoryStorage()
                logger.info("✅ Usando Memory Storage")
            
            # Configurar bot
            self.bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            logger.info("✅ Bot configurado")
            
            # Configurar dispatcher
            self.dp = Dispatcher(storage=self.storage)
            
            # Registrar middlewares
            # Ordem dos middlewares é importante!
            
            # 1. Middleware de autenticação (registra usuários)
            self.dp.message.middleware(AuthMiddleware())
            self.dp.callback_query.middleware(AuthMiddleware())
            
            # 2. Middleware de verificação de canal
            # NÃO aplicar para comandos de admin e callbacks de verificação
            self.dp.message.middleware(
                ChannelMembershipMiddleware(
                    exempt_commands=['/start', '/help', '/admin']
                )
            )
            
            # 3. Middleware de admin (apenas para rotas admin)
            # Este middleware será aplicado nos handlers admin
            # Não registrar globalmente para não bloquear usuários comuns
            
            # Registrar routers na ordem correta
            # IMPORTANTE: Ordem dos routers afeta prioridade
            
            # 1. Admin router (primeiro para comandos admin)
            self.dp.include_router(admin_router)
            logger.info("✅ Admin router registrado")
            
            # 2. Promotion router (para botões do canal)
            self.dp.include_router(promotion_router)
            logger.info("✅ Promotion router registrado")
            
            # 3. Button router (para botões configuráveis)
            self.dp.include_router(button_router)
            logger.info("✅ Button router registrado")
            
            # 4. Callback router (para callbacks gerais)
            self.dp.include_router(callback_router)
            logger.info("✅ Callback router registrado")
            
            # 5. User router (por último para capturar comandos gerais)
            self.dp.include_router(user_router)
            logger.info("✅ User router registrado")
            
            # Configurar workers
            self.scheduler_worker = SchedulerWorker(
                self.bot, 
                self.publication_service
            )
            self.monitoring_worker = MonitoringWorker(
                self.bot, 
                self.alert_service
            )
            logger.info("✅ Workers configurados")
            
            # Configurar comandos do bot
            await self.setup_commands()
            
            logger.info("✅ Setup completo!")
            
        except Exception as e:
            logger.error(f"❌ Erro no setup: {e}")
            raise
    
    async def setup_commands(self):
        """Configura os comandos do bot"""
        try:
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
            
            logger.info("✅ Comandos configurados")
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar comandos: {e}")
    
    async def start(self):
        """Inicia o bot e workers"""
        try:
            await self.setup()
            
            # Iniciar workers em background
            asyncio.create_task(self.scheduler_worker.start())
            asyncio.create_task(self.monitoring_worker.start())
            
            logger.info("🚀 Bot iniciado com sucesso!")
            logger.info(f"📱 Bot username: @{(await self.bot.get_me()).username}")
            logger.info(f"👑 Admin ID: {settings.ADMIN_ID}")
            logger.info(f"📢 Canal: {settings.CHANNEL_ID}")
            
            self.is_running = True
            
            # Iniciar polling
            await self.dp.start_polling(
                self.bot,
                allowed_updates=[
                    "message", 
                    "callback_query", 
                    "chat_member",
                    "edited_message"
                ]
            )
            
        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Para o bot e limpa recursos"""
        try:
            logger.info("👋 Parando bot...")
            
            self.is_running = False
            
            # Parar workers
            if self.scheduler_worker:
                await self.scheduler_worker.stop()
            
            if self.monitoring_worker:
                await self.monitoring_worker.stop()
            
            # Fechar bot
            if self.bot:
                await self.bot.session.close()
            
            # Fechar conexões
            await db_manager.close()
            await redis_manager.close()
            
            logger.info("✅ Bot parado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar bot: {e}")


async def main():
    """Função principal"""
    # Configurar logging
    logger.add(
        f"{settings.LOGS_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log",
        rotation="500 MB",
        retention="30 days",
        level=settings.LOG_LEVEL,
        backtrace=True,
        diagnose=True
    )
    
    bot_app = TechOffersBot()
    
    try:
        await bot_app.start()
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
