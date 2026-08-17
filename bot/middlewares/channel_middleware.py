"""
Middleware de verificação de inscrição no canal
"""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable
from loguru import logger
from datetime import datetime

from database.session import db_manager
from database.models import User, UserStatus
from bot.keyboards.user_keyboards import get_channel_verification_keyboard
from config import settings


class ChannelMembershipMiddleware(BaseMiddleware):
    """
    Middleware para verificação de inscrição no canal
    Bloqueia acesso se usuário não estiver inscrito
    """
    
    def __init__(self, check_exempt_commands: list = None):
        self.check_exempt_commands = check_exempt_commands or [
            '/start', '/help'
        ]
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Processa o evento verificando inscrição no canal"""
        
        # Verificar apenas mensagens de usuários comuns
        if isinstance(event, Message):
            # Ignorar comandos isentos
            if event.text and any(cmd in event.text for cmd in self.check_exempt_commands):
                return await handler(event, data)
            
            # Ignorar mensagens de admin
            if event.from_user.id == settings.ADMIN_ID:
                return await handler(event, data)
            
            # Verificar inscrição no canal
            is_member = await self.check_channel_membership(event)
            
            if not is_member:
                # Bloquear acesso e solicitar inscrição
                await event.answer(
                    "🔒 <b>Acesso necessário</b>\n\n"
                    "Para utilizar o sistema, entre primeiro no nosso canal.\n\n"
                    "Clique no botão abaixo para entrar:",
                    reply_markup=get_channel_verification_keyboard()
                )
                logger.info(f"Blocked access for non-member user {event.from_user.id}")
                return
        
        elif isinstance(event, CallbackQuery):
            # Permitir callback de verificação
            if event.data == "verify_membership":
                return await handler(event, data)
            
            # Ignorar callbacks de admin
            if event.from_user.id == settings.ADMIN_ID:
                return await handler(event, data)
            
            # Verificar inscrição para outros callbacks
            is_member = await self.check_channel_membership(event)
            
            if not is_member:
                await event.answer(
                    "🔒 Entre no canal para usar o bot!",
                    show_alert=True
                )
                return
        
        # Continuar processamento
        return await handler(event, data)
    
    async def check_channel_membership(self, event) -> bool:
        """Verifica se usuário é membro do canal"""
        try:
            user_id = event.from_user.id
            channel_id = settings.CHANNEL_ID
            
            if not channel_id:
                logger.warning("CHANNEL_ID not configured, allowing access")
                return True
            
            # Verificar no Telegram
            chat_member = await event.bot.get_chat_member(
                chat_id=channel_id,
                user_id=user_id
            )
            
            is_member = chat_member.status in ['member', 'administrator', 'creator']
            
            # Atualizar banco de dados
            await self.update_membership_status(user_id, is_member)
            
            return is_member
            
        except Exception as e:
            logger.error(f"Error checking channel membership: {e}")
            # Em caso de erro, permitir acesso temporário
            return True
    
    async def update_membership_status(self, user_id: int, is_member: bool):
        """Atualiza status de inscrição no banco"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                
                if user:
                    user.is_channel_member = is_member
                    user.status = UserStatus.ACTIVE if is_member else UserStatus.PENDING
                    user.last_interaction = datetime.utcnow()
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error updating membership status: {e}")
    
    async def get_cached_membership(self, user_id: int) -> bool:
        """Recupera status de inscrição do cache"""
        try:
            from redis_manager import redis_manager
            
            cache_key = f"membership:{user_id}"
            cached = await redis_manager.get_cache(cache_key)
            
            if cached is not None:
                return cached
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached membership: {e}")
            return None
    
    async def cache_membership(self, user_id: int, is_member: bool, expire_seconds: int = 3600):
        """Cacheia status de inscrição"""
        try:
            from redis_manager import redis_manager
            
            cache_key = f"membership:{user_id}"
            await redis_manager.set_cache(cache_key, is_member, expire_seconds)
            
        except Exception as e:
            logger.error(f"Error caching membership: {e}")
