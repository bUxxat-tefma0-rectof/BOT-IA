"""
Handlers para callbacks do bot
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger
from datetime import datetime
from typing import Optional

from database.session import db_manager
from database.models import User, Product, Alert, AlertStatus, UserInteraction, Publication
from bot.keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_product_keyboard,
    get_product_offer_keyboard,
    get_channel_verification_keyboard,
    get_alerts_keyboard,
    get_categories_keyboard
)
from services.product_service import ProductService
from services.alert_service import AlertService
from services.publication_service import PublicationService
from config import settings

router = Router()
product_service = ProductService()
alert_service = AlertService()
publication_service = PublicationService()


@router.callback_query(F.data == "verify_membership")
async def verify_membership(callback: CallbackQuery):
    """Verifica inscrição no canal"""
    user_id = callback.from_user.id
    
    try:
        # Verificar membro do canal
        chat_member = await callback.bot.get_chat_member(
            chat_id=settings.CHANNEL_ID,
            user_id=user_id
        )
        
        is_member = chat_member.status in ['member', 'administrator', 'creator']
        
        if is_member:
            # Atualizar status do usuário
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if user:
                    user.is_channel_member = True
                    user.status = "active"
                    user.last_interaction = datetime.utcnow()
                    await session.commit()
            
            # Editar mensagem para confirmar
            await callback.message.edit_text(
                "✅ <b>Inscrição confirmada!</b>\n\n"
                f"🎉 Bem-vindo, {callback.from_user.first_name}!\n"
                "Você agora tem acesso ao sistema.",
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.info(f"User {user_id} verified channel membership")
        else:
            # Usuário ainda não é membro
            await callback.answer(
                "❌ Você ainda não entrou no canal. Entre primeiro e depois verifique!",
                show_alert=True
            )
        
    except Exception as e:
        logger.error(f"Error verifying membership: {e}")
        await callback.answer(
            "❌ Erro ao verificar inscrição. Tente novamente.",
            show_alert=True
        )


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Retorna ao menu principal"""
    await state.clear()
    
    await callback.message.edit_text(
        "🔝 <b>MENU PRINCIPAL</b>\n\n"
        "Escolha uma opção:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("activate_alert_"))
async def activate_alert(callback: CallbackQuery):
    """Ativa alerta para produto"""
    user_id = callback.from_user.id
    product_id = int(callback.data.replace("activate_alert_", ""))
    
    # Ativar alerta
    success = await alert_service.toggle_alert(user_id, product_id)
    
    if success:
        # Buscar produto para verificar status
        product = await product_service.get_product_by_id(product_id)
        has_alert = await alert_service.has_active_alert(user_id, product_id)
        
        # Atualizar teclado
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_product_offer_keyboard(product_id, has_alert)
            )
        except:
            pass
        
        # Registrar interação
        await register_interaction(user_id, "activate_alert", product_id)
        
        await callback.answer(
            "🟢 Alerta ativado! Você será notificado quando o preço mudar.",
            show_alert=True
        )
    else:
        await callback.answer(
            "❌ Erro ao ativar alerta. Tente novamente.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("deactivate_alert_"))
async def deactivate_alert(callback: CallbackQuery):
    """Desativa alerta para produto"""
    user_id = callback.from_user.id
    product_id = int(callback.data.replace("deactivate_alert_", ""))
    
    # Desativar alerta
    success = await alert_service.toggle_alert(user_id, product_id)
    
    if success:
        # Atualizar teclado
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_product_offer_keyboard(product_id, False)
            )
        except:
            pass
        
        # Registrar interação
        await register_interaction(user_id, "deactivate_alert", product_id)
        
        await callback.answer(
            "🔴 Alerta desativado.",
            show_alert=True
        )
    else:
        await callback.answer(
            "❌ Erro ao desativar alerta. Tente novamente.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("buy_product_"))
async def buy_product(callback: CallbackQuery):
    """Processa compra do produto"""
    user_id = callback.from_user.id
    product_id = int(callback.data.replace("buy_product_", ""))
    
    # Buscar produto
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer(
            "❌ Produto não encontrado.",
            show_alert=True
        )
        return
    
    # Registrar interação
    await register_interaction(user_id, "click_buy", product_id)
    
    # Mostrar link de compra
    await callback.message.answer(
        f"🛒 <b>COMPRAR AGORA</b>\n\n"
        f"📦 <b>Produto:</b> {product.name}\n"
        f"💰 <b>Preço:</b> R$ {product.current_price:.2f}\n\n"
        f"🔗 <b>Link de compra:</b>\n{product.shopee_link}\n\n"
        "Clique no link acima para comprar na Shopee!"
    )
    
    await callback.answer()


@router.callback_query(F.data == "show_categories")
async def show_categories_callback(callback: CallbackQuery):
    """Mostra categorias disponíveis"""
    categories = await product_service.get_categories()
    
    if not categories:
        await callback.answer("Nenhuma categoria disponível", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📂 <b>CATEGORIAS</b>\n\n"
        "Escolha uma categoria:",
        reply_markup=get_categories_keyboard(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("category_"))
async def show_category_products(callback: CallbackQuery):
    """Mostra produtos de uma categoria"""
    category_id = int(callback.data.replace("category_", ""))
    
    # Buscar produtos da categoria
    products = await product_service.get_products_by_category(category_id)
    
    if not products:
        await callback.message.edit_text(
            "📭 <b>Nenhum produto nesta categoria</b>\n\n"
            "Tente outra categoria:",
            reply_markup=get_categories_keyboard()
        )
        await callback.answer()
        return
    
    # Criar teclado com produtos
    keyboard = []
    for product in products[:10]:
        price_text = f"R$ {product.current_price:.2f}"
        if product.discount_percentage:
            price_text += f" (-{product.discount_percentage:.0f}%)"
        
        keyboard.append([InlineKeyboardButton(
            text=f"📦 {product.name} - {price_text}",
            callback_data=f"view_product_{product.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="show_categories"
    )])
    
    await callback.message.edit_text(
        "📦 <b>PRODUTOS DA CATEGORIA</b>\n\n"
        "Selecione um produto:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_product_"))
async def view_product_callback(callback: CallbackQuery, state: FSMContext):
    """Mostra detalhes do produto"""
    user_id = callback.from_user.id
    product_id = int(callback.data.replace("view_product_", ""))
    
    # Buscar produto
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Produto não encontrado", show_alert=True)
        return
    
    # Verificar alerta
    has_alert = await alert_service.has_active_alert(user_id, product_id)
    
    # Registrar visualização
    await register_interaction(user_id, "view_product", product_id)
    
    # Preparar texto
    product_text = f"📦 <b>{product.name}</b>\n\n"
    
    if product.original_price and product.current_price:
        product_text += f"💰 <b>De:</b> R$ {product.original_price:.2f}\n"
        product_text += f"🔥 <b>Por:</b> R$ {product.current_price:.2f}\n"
        
        if product.discount_percentage:
            product_text += f"📊 <b>Desconto:</b> {product.discount_percentage:.0f}%\n"
    else:
        product_text += f"💰 <b>Preço:</b> R$ {product.current_price:.2f}\n"
    
    if product.description:
        product_text += f"\n📝 <b>Descrição:</b>\n{product.description}\n"
    
    product_text += f"\n🆔 <b>Código:</b> {product.product_code}"
    
    # Editar mensagem
    if product.image_url:
        # Se tem imagem, enviar nova mensagem
        await callback.message.answer_photo(
            photo=product.image_url,
            caption=product_text,
            reply_markup=get_product_offer_keyboard(product_id, has_alert)
        )
    else:
        await callback.message.edit_text(
            product_text,
            reply_markup=get_product_offer_keyboard(product_id, has_alert)
        )
    
    await state.set_state("viewing_product")
    await state.update_data(current_product_id=product_id)
    
    await callback.answer()


@router.callback_query(F.data == "my_alerts")
async def show_my_alerts_callback(callback: CallbackQuery):
    """Mostra alertas do usuário"""
    user_id = callback.from_user.id
    
    # Buscar alertas
    alerts = await alert_service.get_user_alerts(user_id)
    
    if not alerts:
        await callback.message.edit_text(
            "🔔 <b>SEUS ALERTAS</b>\n\n"
            "Você não tem alertas ativos.\n\n"
            "Ative alertas para receber notificações quando os preços caírem!",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return
    
    # Criar teclado com alertas
    keyboard = []
    for alert in alerts[:10]:
        product = alert.product
        status_emoji = "🟢" if alert.status == AlertStatus.ACTIVE else "🔴"
        
        keyboard.append([InlineKeyboardButton(
            text=f"{status_emoji} {product.name}",
            callback_data=f"toggle_alert_{product.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="main_menu"
    )])
    
    await callback.message.edit_text(
        "🔔 <b>SEUS ALERTAS</b>\n\n"
        "Clique em um alerta para ativar/desativar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_alert_"))
async def toggle_alert_callback(callback: CallbackQuery):
    """Alterna alerta do usuário"""
    user_id = callback.from_user.id
    product_id = int(callback.data.replace("toggle_alert_", ""))
    
    success = await alert_service.toggle_alert(user_id, product_id)
    
    if success:
        await callback.answer("✅ Alerta atualizado!", show_alert=True)
        # Atualizar lista
        await show_my_alerts_callback(callback)
    else:
        await callback.answer("❌ Erro ao atualizar alerta", show_alert=True)


async def register_interaction(user_id: int, interaction_type: str, product_id: int = None, publication_id: int = None):
    """Registra interação do usuário"""
    async with db_manager.get_session() as session:
        interaction = UserInteraction(
            user_id=user_id,
            product_id=product_id,
            publication_id=publication_id,
            interaction_type=interaction_type,
            interaction_data={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        session.add(interaction)
        await session.commit()
