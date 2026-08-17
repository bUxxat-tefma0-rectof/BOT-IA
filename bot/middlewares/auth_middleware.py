"""
Middleware de autenticação e autorização
"""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable
from loguru import logger
from datetime import datetime

from database.session import db_manager
from database.models import User, UserStatus
from config import settings


class AuthMiddleware(BaseMiddleware):
    """
    Middleware para autenticação de usuários
    Verifica se o usuário está registrado e atualiza informações
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Processa o evento verificando autenticação"""
        
        # Extrair usuário do evento
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user:
            # Verificar/registrar usuário no banco
            await self.ensure_user_exists(user)
            
            # Adicionar usuário ao data para handlers
            data['db_user'] = await self.get_db_user(user.id)
        
        # Continuar processamento
        return await handler(event, data)
    
    async def ensure_user_exists(self, telegram_user):
        """Garante que o usuário existe no banco de dados"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, telegram_user.id)
                
                if not user:
                    # Criar novo usuário
                    user = User(
                        id=telegram_user.id,
                        telegram_id=telegram_user.id,
                        username=telegram_user.username,
                        first_name=telegram_user.first_name,
                        last_name=telegram_user.last_name,
                        is_channel_member=False,
                        status=UserStatus.PENDING,
                        created_at=datetime.utcnow(),
                        last_interaction=datetime.utcnow()
                    )
                    session.add(user)
                    await session.commit()
                    logger.info(f"New user auto-registered: {telegram_user.id}")
                else:
                    # Atualizar informações do usuário
                    user.username = telegram_user.username
                    user.first_name = telegram_user.first_name
                    user.last_name = telegram_user.last_name
                    user.last_interaction = datetime.utcnow()
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error in AuthMiddleware.ensure_user_exists: {e}")
    
    async def get_db_user(self, user_id: int):
        """Recupera usuário do banco de dados"""
        try:
            async with db_manager.get_session_no_commit() as session:
                user = await session.get(User, user_id)
                return user
        except Exception as e:
            logger.error(f"Error getting user from database: {e}")
            return None


class AdminMiddleware(BaseMiddleware):
    """
    Middleware para autorização administrativa
    Verifica se o usuário tem permissão de admin
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Processa o evento verificando permissões de admin"""
        
        # Extrair usuário do evento
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user:
            # Verificar se é admin
            is_admin = user.id == settings.ADMIN_ID
            
            if not is_admin:
                # Bloquear acesso administrativo
                logger.warning(f"Blocked admin access attempt from user {user.id}")
                
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Acesso negado!", show_alert=True)
                    return
                elif isinstance(event, Message):
                    await event.answer(
                        "⛔ <b>Acesso negado</b>\n\n"
                        "Você não tem permissão para executar esta ação."
                    )
                    return
            
            # Adicionar flag de admin ao data
            data['is_admin'] = is_admin
        
        # Continuar processamento
        return await handler(event, data)
    
    async def check_admin_permission(self, user_id: int) -> bool:
        """Verifica se usuário tem permissão de admin"""
        return user_id == settings.ADMIN_ID
    
    async def log_admin_action(self, admin_id: int, action: str, details: str = None):
        """Registra ação administrativa"""
        try:
            from database.models import AdminLog
            
            async with db_manager.get_session() as session:
                log = AdminLog(
                    admin_id=admin_id,
                    action=action,
                    details=details,
                    created_at=datetime.utcnow()
                )
                session.add(log)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error logging admin action: {e}")
