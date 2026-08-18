"""
Handlers para botões configuráveis do sistema
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from datetime import datetime
from typing import Optional, List, Dict, Any

from database.session import db_manager
from database.models import (
    Product, ButtonConfig, UserInteraction, 
    Alert, AlertStatus
)
from services.product_service import ProductService
from services.alert_service import AlertService
from config import settings

router = Router()
product_service = ProductService()
alert_service = AlertService()


@router.callback_query(F.data.startswith("custom_button_"))
async def handle_custom_button(callback: CallbackQuery):
    """
    Handler para botões customizados configurados pelo admin
    """
    try:
        button_id = int(callback.data.replace("custom_button_", ""))
        
        # Buscar configuração do botão
        button_config = await get_button_config(button_id)
        
        if not button_config:
            await callback.answer("❌ Botão não encontrado", show_alert=True)
            return
        
        # Executar ação baseada no tipo
        action_type = button_config.action_type
        
        if action_type == "alert":
            await handle_alert_button(callback, button_config)
        elif action_type == "buy":
            await handle_buy_button(callback, button_config)
        elif action_type == "support":
            await handle_support_button(callback, button_config)
        elif action_type == "info":
            await handle_info_button(callback, button_config)
        elif action_type == "custom":
            await handle_custom_action(callback, button_config)
        else:
            await callback.answer("❌ Ação não suportada", show_alert=True)
            
    except Exception as e:
        logger.error(f"Erro ao processar botão customizado: {e}")
        await callback.answer("❌ Erro ao processar", show_alert=True)


async def handle_alert_button(callback: CallbackQuery, button_config: ButtonConfig):
    """Processa botão de alerta"""
    try:
        product_id = button_config.action_data.get('product_id')
        
        if not product_id:
            await callback.answer("❌ Produto não configurado", show_alert=True)
            return
        
        user_id = callback.from_user.id
        
        # Alternar alerta
        has_alert = await alert_service.has_active_alert(user_id, product_id)
        
        if has_alert:
            await alert_service.toggle_alert(user_id, product_id)
            await callback.answer("🔴 Alerta desativado!", show_alert=True)
        else:
            await alert_service.toggle_alert(user_id, product_id)
            await callback.answer("🟢 Alerta ativado!", show_alert=True)
        
        # Registrar interação
        await register_button_interaction(user_id, product_id, "alert_toggle")
        
    except Exception as e:
        logger.error(f"Erro no botão de alerta: {e}")
        await callback.answer("❌ Erro", show_alert=True)


async def handle_buy_button(callback: CallbackQuery, button_config: ButtonConfig):
    """Processa botão de compra"""
    try:
        product_id = button_config.action_data.get('product_id')
        
        if not product_id:
            await callback.answer("❌ Produto não configurado", show_alert=True)
            return
        
        product = await product_service.get_product_by_id(product_id)
        
        if not product:
            await callback.answer("❌ Produto não encontrado", show_alert=True)
            return
        
        # Registrar clique
        await register_button_interaction(callback.from_user.id, product_id, "buy_click")
        
        # Enviar link de compra
        await callback.message.answer(
            f"🛒 <b>COMPRAR AGORA</b>\n\n"
            f"📦 <b>Produto:</b> {product.name}\n"
            f"💰 <b>Preço:</b> R$ {product.current_price:.2f}\n\n"
            f"🔗 <b>Link:</b>\n{product.shopee_link}"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Erro no botão de compra: {e}")
        await callback.answer("❌ Erro", show_alert=True)


async def handle_support_button(callback: CallbackQuery, button_config: ButtonConfig):
    """Processa botão de suporte"""
    try:
        support_text = (
            "💬 <b>SUPORTE TÉCNICO</b>\n\n"
            "📧 <b>Email:</b> suporte@techoffers.com\n"
            "⏰ <b>Horário:</b> Seg-Sex, 9h às 18h\n"
            "📱 <b>Telegram:</b> @techoffers_suporte\n\n"
            "Descreva sua dúvida que responderemos em breve!"
        )
        
        await callback.message.answer(support_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Erro no botão de suporte: {e}")
        await callback.answer("❌ Erro", show_alert=True)


async def handle_info_button(callback: CallbackQuery, button_config: ButtonConfig):
    """Processa botão de informação"""
    try:
        info_text = button_config.action_data.get('text', 'Sem informações adicionais')
        
        await callback.message.answer(info_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Erro no botão de info: {e}")
        await callback.answer("❌ Erro", show_alert=True)


async def handle_custom_action(callback: CallbackQuery, button_config: ButtonConfig):
    """Processa ação customizada"""
    try:
        action = button_config.action_data.get('action')
        
        if action == "show_offers":
            # Mostrar ofertas
            from bot.handlers.user_handlers import cmd_offers
            await cmd_offers(callback.message)
        elif action == "show_categories":
            # Mostrar categorias
            from bot.handlers.user_handlers import cmd_categories
            await cmd_categories(callback.message)
        elif action == "show_alerts":
            # Mostrar alertas
            from bot.handlers.user_handlers import cmd_alerts
            await cmd_alerts(callback.message)
        else:
            await callback.answer("❌ Ação não configurada", show_alert=True)
            
    except Exception as e:
        logger.error(f"Erro na ação customizada: {e}")
        await callback.answer("❌ Erro", show_alert=True)


async def get_button_config(button_id: int) -> Optional[ButtonConfig]:
    """Busca configuração do botão"""
    try:
        from sqlalchemy import select
        
        async with db_manager.get_session_no_commit() as session:
            result = await session.execute(
                select(ButtonConfig)
                .where(ButtonConfig.id == button_id)
                .where(ButtonConfig.is_active == True)
            )
            button = result.scalar_one_or_none()
            
            return button
            
    except Exception as e:
        logger.error(f"Erro ao buscar configuração do botão: {e}")
        return None


async def register_button_interaction(
    user_id: int,
    product_id: int,
    action_type: str
):
    """Registra interação do botão"""
    try:
        async with db_manager.get_session() as session:
            interaction = UserInteraction(
                user_id=user_id,
                product_id=product_id,
                interaction_type=f"button_{action_type}",
                interaction_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "custom_button"
                }
            )
            
            session.add(interaction)
            await session.commit()
            
    except Exception as e:
        logger.error(f"Erro ao registrar interação do botão: {e}")


@router.callback_query(F.data.startswith("config_button_"))
async def handle_configured_button(callback: CallbackQuery):
    """
    Handler para botões configurados dinamicamente
    Formato: config_button_{action}_{product_id}
    """
    try:
        parts = callback.data.split("_")
        
        if len(parts) >= 4:
            action = parts[2]
            product_id = int(parts[3])
            
            if action == "alert":
                # Alternar alerta
                user_id = callback.from_user.id
                has_alert = await alert_service.has_active_alert(user_id, product_id)
                
                await alert_service.toggle_alert(user_id, product_id)
                
                if has_alert:
                    await callback.answer("🔴 Alerta desativado!", show_alert=True)
                else:
                    await callback.answer("🟢 Alerta ativado!", show_alert=True)
                    
            elif action == "buy":
                # Mostrar link de compra
                product = await product_service.get_product_by_id(product_id)
                
                if product:
                    await callback.message.answer(
                        f"🛒 <b>COMPRAR AGORA</b>\n\n"
                        f"📦 {product.name}\n"
                        f"💰 R$ {product.current_price:.2f}\n\n"
                        f"🔗 {product.shopee_link}"
                    )
                    await callback.answer()
                else:
                    await callback.answer("❌ Produto não encontrado", show_alert=True)
            
            elif action == "info":
                # Mostrar informações
                product = await product_service.get_product_by_id(product_id)
                
                if product:
                    await callback.message.answer(
                        f"📦 <b>{product.name}</b>\n\n"
                        f"{product.description or 'Sem descrição'}"
                    )
                    await callback.answer()
                else:
                    await callback.answer("❌ Produto não encontrado", show_alert=True)
            
            else:
                await callback.answer("❌ Ação não suportada", show_alert=True)
        else:
            await callback.answer("❌ Dados inválidos", show_alert=True)
            
    except Exception as e:
        logger.error(f"Erro no botão configurado: {e}")
        await callback.answer("❌ Erro", show_alert=True)
