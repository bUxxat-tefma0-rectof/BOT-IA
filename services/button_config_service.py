"""
Serviço de configuração de botões
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete
from loguru import logger
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.session import db_manager
from database.models import ButtonConfig
from redis_manager import redis_manager


class ButtonConfigService:
    """Serviço para configuração de botões"""
    
    def __init__(self):
        self.cache_prefix = "button:"
        self.cache_ttl = 3600
    
    async def create_button(self, button_data: Dict[str, Any]) -> Optional[ButtonConfig]:
        """Cria novo botão"""
        try:
            async with db_manager.get_session() as session:
                button = ButtonConfig(
                    name=button_data.get('name'),
                    text=button_data.get('text'),
                    emoji=button_data.get('emoji'),
                    action_type=button_data.get('action_type', 'callback'),
                    action_data=button_data.get('action_data'),
                    url=button_data.get('url'),
                    callback_data=button_data.get('callback_data'),
                    position=button_data.get('position', 0),
                    row=button_data.get('row', 0),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(button)
                await session.commit()
                
                logger.info(f"Button created: {button.name}")
                return button
                
        except Exception as e:
            logger.error(f"Error creating button: {e}")
            return None
    
    async def get_active_buttons(self) -> List[ButtonConfig]:
        """Busca botões ativos ordenados por posição"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(ButtonConfig)
                    .where(ButtonConfig.is_active == True)
                    .order_by(ButtonConfig.row, ButtonConfig.position)
                )
                buttons = result.scalars().all()
                
                return list(buttons)
                
        except Exception as e:
            logger.error(f"Error getting active buttons: {e}")
            return []
    
    async def build_keyboard(self, product_id: int = None) -> InlineKeyboardMarkup:
        """
        Constrói teclado a partir das configurações
        
        Args:
            product_id: ID do produto (para callbacks dinâmicos)
        
        Returns:
            InlineKeyboardMarkup: Teclado configurado
        """
        try:
            buttons = await self.get_active_buttons()
            
            if not buttons:
                # Retornar teclado padrão
                return self._get_default_keyboard(product_id)
            
            # Agrupar botões por linha
            keyboard = {}
            for button in buttons:
                row = button.row
                if row not in keyboard:
                    keyboard[row] = []
                
                # Configurar botão
                if button.action_type == 'url' and button.url:
                    inline_button = InlineKeyboardButton(
                        text=f"{button.emoji or ''} {button.text}".strip(),
                        url=button.url
                    )
                elif button.action_type == 'callback' and button.callback_data:
                    callback_data = button.callback_data
                    
                    # Substituir variáveis no callback
                    if product_id and '{product_id}' in callback_data:
                        callback_data = callback_data.replace('{product_id}', str(product_id))
                    
                    inline_button = InlineKeyboardButton(
                        text=f"{button.emoji or ''} {button.text}".strip(),
                        callback_data=callback_data
                    )
                else:
                    continue
                
                keyboard[row].append(inline_button)
            
            # Converter para lista de listas
            keyboard_list = []
            for row in sorted(keyboard.keys()):
                keyboard_list.append(keyboard[row])
            
            return InlineKeyboardMarkup(inline_keyboard=keyboard_list)
            
        except Exception as e:
            logger.error(f"Error building keyboard: {e}")
            return self._get_default_keyboard(product_id)
    
    def _get_default_keyboard(self, product_id: int = None) -> InlineKeyboardMarkup:
        """Retorna teclado padrão"""
        keyboard = []
        
        if product_id:
            keyboard.append([
                InlineKeyboardButton(
                    text="🛒 COMPRAR AGORA",
                    callback_data=f"buy_product_{product_id}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text="🔔 ATIVAR ALERTA",
                    callback_data=f"activate_alert_{product_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                text="💬 SUPORTE",
                callback_data="support"
            )
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    async def create_default_buttons(self):
        """Cria botões padrão do sistema"""
        default_buttons = [
            {
                'name': 'buy_now',
                'text': 'COMPRAR AGORA',
                'emoji': '🛒',
                'action_type': 'callback',
                'callback_data': 'buy_product_{product_id}',
                'position': 0,
                'row': 0
            },
            {
                'name': 'activate_alert',
                'text': 'ATIVAR ALERTA',
                'emoji': '🔔',
                'action_type': 'callback',
                'callback_data': 'activate_alert_{product_id}',
                'position': 0,
                'row': 1
            },
            {
                'name': 'support',
                'text': 'SUPORTE',
                'emoji': '💬',
                'action_type': 'callback',
                'callback_data': 'support',
                'position': 0,
                'row': 2
            }
        ]
        
        for button_data in default_buttons:
            await self.create_button(button_data)
        
        logger.info("Default buttons created")
    
    async def update_button(self, button_id: int, update_data: Dict[str, Any]) -> bool:
        """Atualiza botão"""
        try:
            async with db_manager.get_session() as session:
                button = await session.get(ButtonConfig, button_id)
                
                if not button:
                    return False
                
                for key, value in update_data.items():
                    if hasattr(button, key):
                        setattr(button, key, value)
                
                button.updated_at = datetime.utcnow()
                await session.commit()
                
                # Limpar cache
                await redis_manager.clear_cache_pattern(f"{self.cache_prefix}*")
                
                logger.info(f"Button updated: {button_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating button: {e}")
            return False
