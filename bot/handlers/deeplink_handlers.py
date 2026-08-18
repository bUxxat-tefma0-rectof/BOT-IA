"""
Handlers para deeplinks do bot
Sistema que identifica origem do usuário e mostra oferta correta
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from loguru import logger
from datetime import datetime
from typing import Optional

from database.session import db_manager
from database.models import (
    User, Product, SourceTracking, 
    UserInteraction, Alert, AlertStatus
)
from services.product_service import ProductService
from services.alert_service import AlertService
from bot.keyboards.user_keyboards import (
    get_product_offer_keyboard,
    get_channel_verification_keyboard,
    get_main_menu_keyboard
)
from config import settings

router = Router()
product_service = ProductService()
alert_service = AlertService()


@router.message(CommandStart(deep_link=True))
async def handle_deeplink(message: Message, state: FSMContext, command=None):
    """
    Handler para deeplinks do bot
    Identifica a origem e mostra a oferta correta
    """
    try:
        user_id = message.from_user.id
        args = message.text.split()
        
        if len(args) < 2:
            # Sem parâmetros, mostrar menu normal
            await message.answer(
                f"👋 Bem-vindo, {message.from_user.first_name}!",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Extrair parâmetro do deeplink
        deeplink_param = args[1]
        
        logger.info(f"Deeplink recebido de {user_id}: {deeplink_param}")
        
        # Processar diferentes tipos de deeplinks
        if deeplink_param.startswith("oferta_"):
            # Deeplink de oferta específica
            product_code = deeplink_param.replace("oferta_", "")
            await process_offer_deeplink(message, product_code, state)
            
        elif deeplink_param.startswith("categoria_"):
            # Deeplink de categoria
            category_id = deeplink_param.replace("categoria_", "")
            await process_category_deeplink(message, category_id)
            
        elif deeplink_param.startswith("promo_"):
            # Deeplink de promoção
            product_code = deeplink_param.replace("promo_", "")
            await process_promotion_deeplink(message, product_code, state)
            
        else:
            # Deeplink desconhecido
            await message.answer(
                "❌ Link inválido ou expirado.",
                reply_markup=get_main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Erro ao processar deeplink: {e}")
        await message.answer(
            "❌ Erro ao processar link. Tente novamente.",
            reply_markup=get_main_menu_keyboard()
        )


async def process_offer_deeplink(
    message: Message,
    product_code: str,
    state: FSMContext
):
    """
    Processa deeplink de oferta
    Usuário clicou em "IR PARA OFERTA" no canal
    """
    try:
        user_id = message.from_user.id
        
        logger.info(f"Usuário {user_id} acessou oferta {product_code}")
        
        # Verificar inscrição no canal
        is_member = await check_channel_membership(message, user_id)
        
        if not is_member:
            await message.answer(
                "🔒 <b>Acesso necessário</b>\n\n"
                "Para ver esta oferta, entre primeiro no nosso canal:",
                reply_markup=get_channel_verification_keyboard()
            )
            return
        
        # Buscar produto pelo código
        product = await product_service.get_product_by_code(product_code)
        
        if not product:
            await message.answer(
                "❌ <b>Oferta não encontrada</b>\n\n"
                "Esta oferta pode ter expirado ou sido removida.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # REGISTRAR ORIGEM
        await register_origin(
            user_id=user_id,
            source_type="channel_deeplink",
            product_id=product.id,
            product_code=product_code,
            source_id=f"channel_{settings.CHANNEL_ID}"
        )
        
        # Registrar visualização
        await register_interaction(
            user_id=user_id,
            interaction_type="view_product_deeplink",
            product_id=product.id
        )
        
        # Verificar alerta
        has_alert = await alert_service.has_active_alert(user_id, product.id)
        
        # Mostrar produto
        product_text = format_product_text(product)
        
        if product.image_url:
            await message.answer_photo(
                photo=product.image_url,
                caption=product_text,
                reply_markup=get_product_offer_keyboard(product.id, has_alert)
            )
        else:
            await message.answer(
                product_text,
                reply_markup=get_product_offer_keyboard(product.id, has_alert)
            )
        
        # Salvar estado
        await state.set_state("viewing_product")
        await state.update_data(
            current_product_id=product.id,
            product_code=product_code,
            source="channel_deeplink"
        )
        
    except Exception as e:
        logger.error(f"Erro ao processar oferta deeplink: {e}")
        await message.answer(
            "❌ Erro ao carregar oferta.",
            reply_markup=get_main_menu_keyboard()
        )


async def process_category_deeplink(message: Message, category_id: str):
    """Processa deeplink de categoria"""
    try:
        # Buscar produtos da categoria
        products = await product_service.get_products_by_category(int(category_id))
        
        if not products:
            await message.answer(
                "📭 Nenhum produto nesta categoria.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Mostrar produtos
        from bot.keyboards.user_keyboards import get_categories_keyboard
        
        products_text = "📦 <b>PRODUTOS DA CATEGORIA</b>\n\n"
        
        for i, product in enumerate(products[:10], 1):
            products_text += f"{i}. {product.name}\n"
            products_text += f"   💰 R$ {product.current_price:.2f}\n\n"
        
        await message.answer(
            products_text,
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Erro no deeplink de categoria: {e}")


async def process_promotion_deeplink(
    message: Message,
    product_code: str,
    state: FSMContext
):
    """Processa deeplink de promoção"""
    try:
        # Similar ao deeplink de oferta, mas com foco em promoção
        await process_offer_deeplink(message, product_code, state)
        
    except Exception as e:
        logger.error(f"Erro no deeplink de promoção: {e}")


async def check_channel_membership(message: Message, user_id: int) -> bool:
    """Verifica inscrição no canal"""
    try:
        channel_id = settings.CHANNEL_ID
        
        if not channel_id:
            return True
        
        chat_member = await message.bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )
        
        is_member = chat_member.status in ['member', 'administrator', 'creator']
        
        # Atualizar banco
        async with db_manager.get_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.is_channel_member = is_member
                user.last_interaction = datetime.utcnow()
                await session.commit()
        
        return is_member
        
    except Exception as e:
        logger.error(f"Erro ao verificar inscrição: {e}")
        return True


async def register_origin(
    user_id: int,
    source_type: str,
    product_id: int,
    product_code: str,
    source_id: str = None
):
    """Registra origem do usuário"""
    try:
        async with db_manager.get_session() as session:
            tracking = SourceTracking(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                product_code=product_code,
                tracking_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "product_id": product_id,
                    "channel": settings.CHANNEL_ID
                }
            )
            
            session.add(tracking)
            await session.commit()
            
            logger.info(f"Origem registrada: {source_type} - {product_code}")
            
    except Exception as e:
        logger.error(f"Erro ao registrar origem: {e}")


async def register_interaction(
    user_id: int,
    interaction_type: str,
    product_id: int = None
):
    """Registra interação"""
    try:
        async with db_manager.get_session() as session:
            interaction = UserInteraction(
                user_id=user_id,
                product_id=product_id,
                interaction_type=interaction_type,
                interaction_data={
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            session.add(interaction)
            await session.commit()
            
    except Exception as e:
        logger.error(f"Erro ao registrar interação: {e}")


def format_product_text(product: Product) -> str:
    """Formata texto do produto"""
    try:
        text = f"📦 <b>{product.name}</b>\n\n"
        
        if product.original_price and product.current_price:
            text += f"💰 <b>De:</b> R$ {product.original_price:.2f}\n"
            text += f"🔥 <b>Por:</b> R$ {product.current_price:.2f}\n"
            
            if product.discount_percentage:
                text += f"📊 <b>Desconto:</b> {product.discount_percentage:.0f}%\n"
        else:
            text += f"💰 <b>Preço:</b> R$ {product.current_price:.2f}\n"
        
        if product.description:
            text += f"\n📝 <b>Descrição:</b>\n{product.description}\n"
        
        text += f"\n🆔 <b>Código:</b> {product.product_code}"
        
        return text
        
    except Exception as e:
        logger.error(f"Erro ao formatar produto: {e}")
        return f"📦 {product.name}"
