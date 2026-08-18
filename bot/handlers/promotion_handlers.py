"""
Handlers para botões de promoção no canal
Sistema que edita mensagens do canal quando usuário ativa/desativa promoção
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
from datetime import datetime
from typing import Optional

from database.session import db_manager
from database.models import (
    User, Product, Alert, AlertStatus, 
    Publication, UserInteraction
)
from services.alert_service import AlertService
from services.product_service import ProductService
from services.publication_service import PublicationService
from config import settings

router = Router()
alert_service = AlertService()
product_service = ProductService()
publication_service = PublicationService()


@router.callback_query(F.data.startswith("activate_promotion_"))
async def activate_promotion_channel(callback: CallbackQuery):
    """
    Ativa promoção quando usuário clica no botão do canal
    EDITA a mensagem original do canal
    """
    try:
        user_id = callback.from_user.id
        product_id = int(callback.data.replace("activate_promotion_", ""))
        
        logger.info(f"Usuário {user_id} ativando promoção do produto {product_id}")
        
        # Verificar se usuário está inscrito no canal
        is_member = await check_channel_membership(callback.bot, user_id)
        
        if not is_member:
            await callback.answer(
                "🔒 Entre no canal primeiro para ativar a promoção!",
                show_alert=True
            )
            return
        
        # Buscar produto
        product = await product_service.get_product_by_id(product_id)
        
        if not product:
            await callback.answer(
                "❌ Produto não encontrado!",
                show_alert=True
            )
            return
        
        # Verificar se usuário já tem alerta ativo
        has_alert = await alert_service.has_active_alert(user_id, product_id)
        
        if has_alert:
            # Desativar alerta
            await alert_service.toggle_alert(user_id, product_id)
            alert_status = False
            message = "🔴 Promoção desativada!"
        else:
            # Ativar alerta
            await alert_service.toggle_alert(user_id, product_id)
            alert_status = True
            message = "🟢 Promoção ativada! Você será notificado sobre mudanças de preço."
        
        # Registrar interação
        await register_interaction(
            user_id=user_id,
            interaction_type="toggle_promotion_channel",
            product_id=product_id
        )
        
        # Responder ao usuário
        await callback.answer(message, show_alert=True)
        
        # EDITAR a mensagem do canal
        await edit_channel_message_buttons(
            bot=callback.bot,
            product_id=product_id,
            has_alert=alert_status
        )
        
        # Enviar confirmação privada para o usuário
        if alert_status:
            await send_private_confirmation(callback, product, True)
        
        logger.info(f"Promoção {'ativada' if alert_status else 'desativada'} para usuário {user_id}")
        
    except Exception as e:
        logger.error(f"Erro ao ativar promoção: {e}")
        await callback.answer(
            "❌ Erro ao processar sua solicitação. Tente novamente.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("deactivate_promotion_"))
async def deactivate_promotion_channel(callback: CallbackQuery):
    """
    Desativa promoção quando usuário clica no botão do canal
    """
    try:
        user_id = callback.from_user.id
        product_id = int(callback.data.replace("deactivate_promotion_", ""))
        
        logger.info(f"Usuário {user_id} desativando promoção do produto {product_id}")
        
        # Desativar alerta
        await alert_service.toggle_alert(user_id, product_id)
        
        # Registrar interação
        await register_interaction(
            user_id=user_id,
            interaction_type="deactivate_promotion_channel",
            product_id=product_id
        )
        
        await callback.answer(
            "🔴 Promoção desativada!",
            show_alert=True
        )
        
        # Editar mensagem do canal
        await edit_channel_message_buttons(
            bot=callback.bot,
            product_id=product_id,
            has_alert=False
        )
        
    except Exception as e:
        logger.error(f"Erro ao desativar promoção: {e}")
        await callback.answer(
            "❌ Erro ao processar. Tente novamente.",
            show_alert=True
        )


async def edit_channel_message_buttons(
    bot: Bot,
    product_id: int,
    has_alert: bool
):
    """
    Edita os botões da mensagem no canal
    Esta é a função CRÍTICA que edita a mensagem original
    
    Args:
        bot: Instância do bot
        product_id: ID do produto
        has_alert: Se usuário tem alerta ativo
    """
    try:
        # Buscar publicações ativas deste produto
        publications = await get_product_publications(product_id)
        
        if not publications:
            logger.warning(f"Nenhuma publicação encontrada para produto {product_id}")
            return
        
        # Buscar produto para montar botões
        product = await product_service.get_product_by_id(product_id)
        
        if not product:
            return
        
        channel_id = settings.CHANNEL_ID
        
        # Para cada publicação, editar os botões
        for publication in publications:
            if publication.channel_message_id:
                try:
                    # Criar novo teclado com botão atualizado
                    new_keyboard = await create_updated_keyboard(product)
                    
                    # Editar mensagem no canal
                    await bot.edit_message_reply_markup(
                        chat_id=channel_id,
                        message_id=publication.channel_message_id,
                        reply_markup=new_keyboard
                    )
                    
                    logger.info(
                        f"✅ Mensagem do canal editada: "
                        f"message_id={publication.channel_message_id}"
                    )
                    
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e):
                        logger.info("Mensagem não modificada (mesmo conteúdo)")
                    else:
                        logger.error(f"Erro Telegram ao editar mensagem: {e}")
                        
                except Exception as e:
                    logger.error(f"Erro ao editar mensagem do canal: {e}")
                    
    except Exception as e:
        logger.error(f"Erro em edit_channel_message_buttons: {e}")


async def create_updated_keyboard(product: Product) -> InlineKeyboardMarkup:
    """
    Cria teclado atualizado para a mensagem do canal
    
    Args:
        product: Produto da publicação
    
    Returns:
        InlineKeyboardMarkup: Teclado atualizado
    """
    try:
        keyboard = []
        
        # Botão de ativar/desativar promoção
        # Este botão sempre mostra "ATIVAR PROMOÇÃO" pois cada usuário
        # tem seu próprio estado de alerta
        keyboard.append([
            InlineKeyboardButton(
                text="⚪ ATIVAR PROMOÇÃO",
                callback_data=f"activate_promotion_{product.id}"
            )
        ])
        
        # Botão de ir para oferta (deeplink para o bot)
        bot_username = await get_bot_username()
        deeplink = f"https://t.me/{bot_username}?start=oferta_{product.product_code}"
        
        keyboard.append([
            InlineKeyboardButton(
                text="🛒 IR PARA OFERTA",
                url=deeplink
            )
        ])
        
        # Botão de suporte
        keyboard.append([
            InlineKeyboardButton(
                text="💬 SUPORTE",
                url="https://t.me/techoffers_suporte"
            )
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
        
    except Exception as e:
        logger.error(f"Erro ao criar teclado atualizado: {e}")
        return None


async def get_product_publications(product_id: int) -> list:
    """Busca publicações ativas de um produto"""
    try:
        from sqlalchemy import select
        
        async with db_manager.get_session_no_commit() as session:
            result = await session.execute(
                select(Publication)
                .where(Publication.product_id == product_id)
                .where(Publication.status == "published")
                .order_by(Publication.published_at.desc())
            )
            publications = result.scalars().all()
            
            return list(publications)
            
    except Exception as e:
        logger.error(f"Erro ao buscar publicações: {e}")
        return []


async def get_bot_username() -> str:
    """Busca username do bot"""
    try:
        from bot.main import TechOffersBot
        # Não podemos criar nova instância aqui
        # Retornar username padrão
        return "TechOffersBot"
    except:
        return "TechOffersBot"


async def check_channel_membership(bot: Bot, user_id: int) -> bool:
    """Verifica se usuário é membro do canal"""
    try:
        channel_id = settings.CHANNEL_ID
        
        if not channel_id:
            return True
        
        chat_member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )
        
        return chat_member.status in ['member', 'administrator', 'creator']
        
    except Exception as e:
        logger.error(f"Erro ao verificar inscrição: {e}")
        return True


async def register_interaction(
    user_id: int,
    interaction_type: str,
    product_id: int = None,
    publication_id: int = None
):
    """Registra interação do usuário"""
    try:
        async with db_manager.get_session() as session:
            interaction = UserInteraction(
                user_id=user_id,
                product_id=product_id,
                publication_id=publication_id,
                interaction_type=interaction_type,
                interaction_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "channel_button"
                }
            )
            
            session.add(interaction)
            await session.commit()
            
    except Exception as e:
        logger.error(f"Erro ao registrar interação: {e}")


async def send_private_confirmation(
    callback: CallbackQuery,
    product: Product,
    is_activated: bool
):
    """
    Envia confirmação privada para o usuário
    
    Args:
        callback: Callback original
        product: Produto da promoção
        is_activated: Se foi ativado
    """
    try:
        if is_activated:
            message_text = (
                f"🟢 <b>PROMOÇÃO ATIVADA!</b>\n\n"
                f"📦 <b>Produto:</b> {product.name}\n"
                f"💰 <b>Preço atual:</b> R$ {product.current_price:.2f}\n"
                f"🎯 <b>Preço alvo:</b> R$ {product.target_price:.2f}\n\n"
                f"✅ Você será notificado quando o preço mudar!\n\n"
                f"🔗 <a href='{product.shopee_link}'>Ver produto na Shopee</a>"
            )
        else:
            message_text = (
                f"🔴 <b>PROMOÇÃO DESATIVADA</b>\n\n"
                f"📦 <b>Produto:</b> {product.name}\n\n"
                f"Você não receberá mais notificações deste produto."
            )
        
        # Enviar mensagem privada
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=message_text
        )
        
    except Exception as e:
        logger.error(f"Erro ao enviar confirmação privada: {e}")
