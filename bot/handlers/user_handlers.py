"""
Handlers para interações de usuário
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional

from database.session import db_manager
from database.models import User, UserStatus, Product, Alert, AlertStatus
from bot.keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_product_keyboard,
    get_categories_keyboard,
    get_alerts_keyboard,
    get_channel_verification_keyboard,
    get_product_offer_keyboard
)
from services.product_service import ProductService
from services.alert_service import AlertService
from config import settings

router = Router()
product_service = ProductService()
alert_service = AlertService()


class UserStates(StatesGroup):
    """Estados do usuário"""
    browsing_products = State()
    viewing_product = State()
    viewing_alerts = State()
    selecting_category = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Handler para o comando /start
    Verifica inscrição no canal e origem do usuário
    """
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    logger.info(f"User {user_id} ({user_name}) started the bot")
    
    # Verificar se veio de uma oferta específica
    args = message.text.split()
    if len(args) > 1:
        # Usuário veio de uma oferta específica
        product_code = args[1].replace("oferta_", "")
        await process_product_deeplink(message, product_code, state)
        return
    
    # Registrar ou atualizar usuário
    async with db_manager.get_session() as session:
        user = await session.get(User, user_id)
        
        if not user:
            user = User(
                id=user_id,
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                created_at=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
            logger.info(f"New user registered: {user_id}")
        
        user.last_interaction = datetime.utcnow()
        await session.commit()
    
    # Verificar inscrição no canal
    is_member = await check_channel_membership(message.bot, user_id)
    
    if not is_member:
        await message.answer(
            "🔒 <b>Acesso necessário</b>\n\n"
            "Para utilizar o sistema, entre primeiro no nosso canal.\n\n"
            "Clique no botão abaixo para entrar:",
            reply_markup=get_channel_verification_keyboard()
        )
        return
    
    # Usuário verificado
    await message.answer(
        f"✅ <b>Bem-vindo, {message.from_user.first_name}!</b>\n\n"
        f"🎉 Inscrição confirmada!\n"
        f"🔥 Você agora tem acesso ao nosso sistema de ofertas tecnológicas.\n\n"
        f"Escolha uma opção abaixo:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handler para o comando /help"""
    help_text = (
        "📚 <b>Central de Ajuda</b>\n\n"
        "🔍 <b>Como usar o bot:</b>\n"
        "• Use /offers para ver ofertas ativas\n"
        "• Use /alerts para gerenciar seus alertas\n"
        "• Use /categories para navegar por categorias\n\n"
        "🔔 <b>Alertas de preço:</b>\n"
        "• Ative alertas para produtos que deseja acompanhar\n"
        "• Receba notificações quando o preço atingir seu alvo\n\n"
        "💬 <b>Suporte:</b>\n"
        "• Entre em contato pelo botão de suporte\n"
        "• Nossa equipe responde em até 24h\n\n"
        "🛒 <b>Compras:</b>\n"
        "• Todos os produtos são de lojas verificadas\n"
        "• Links diretos para as melhores ofertas"
    )
    
    await message.answer(help_text, reply_markup=get_main_menu_keyboard())


@router.message(Command("offers"))
async def cmd_offers(message: Message, state: FSMContext):
    """Handler para o comando /offers - mostra ofertas ativas"""
    user_id = message.from_user.id
    
    # Verificar inscrição
    is_member = await check_channel_membership(message.bot, user_id)
    if not is_member:
        await message.answer(
            "🔒 <b>Acesso necessário</b>\n\n"
            "Para ver as ofertas, entre primeiro no nosso canal:",
            reply_markup=get_channel_verification_keyboard()
        )
        return
    
    # Buscar ofertas ativas
    offers = await product_service.get_active_offers()
    
    if not offers:
        await message.answer(
            "📭 <b>Nenhuma oferta ativa no momento</b>\n\n"
            "Volte mais tarde ou ative alertas para ser notificado!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Mostrar lista de ofertas
    offers_text = "🔥 <b>OFERTAS ATIVAS</b>\n\n"
    
    for i, product in enumerate(offers[:10], 1):
        discount = product.discount_percentage
        if discount:
            offers_text += f"{i}. <b>{product.name}</b>\n"
            offers_text += f"   💰 De: R$ {product.original_price:.2f}\n"
            offers_text += f"   🔥 Por: R$ {product.current_price:.2f}\n"
            offers_text += f"   📊 Desconto: {discount:.0f}%\n\n"
        else:
            offers_text += f"{i}. <b>{product.name}</b>\n"
            offers_text += f"   💰 Preço: R$ {product.current_price:.2f}\n\n"
    
    await message.answer(
        offers_text,
        reply_markup=get_categories_keyboard()
    )
    
    await state.set_state(UserStates.browsing_products)


@router.message(Command("alerts"))
async def cmd_alerts(message: Message, state: FSMContext):
    """Handler para o comando /alerts - mostra alertas do usuário"""
    user_id = message.from_user.id
    
    # Verificar inscrição
    is_member = await check_channel_membership(message.bot, user_id)
    if not is_member:
        await message.answer(
            "🔒 <b>Acesso necessário</b>\n\n"
            "Para ver seus alertas, entre primeiro no nosso canal:",
            reply_markup=get_channel_verification_keyboard()
        )
        return
    
    # Buscar alertas do usuário
    alerts = await alert_service.get_user_alerts(user_id)
    
    if not alerts:
        await message.answer(
            "🔔 <b>Seus Alertas</b>\n\n"
            "Você não tem alertas ativos.\n\n"
            "Ative alertas para receber notificações quando os preços dos produtos caírem!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Mostrar alertas
    alerts_text = "🔔 <b>SEUS ALERTAS</b>\n\n"
    
    for i, alert in enumerate(alerts, 1):
        product = alert.product
        if alert.status == AlertStatus.ACTIVE:
            status_emoji = "🟢"
            status_text = "Ativo"
        else:
            status_emoji = "🔴"
            status_text = "Inativo"
        
        alerts_text += f"{i}. {status_emoji} <b>{product.name}</b>\n"
        alerts_text += f"   💰 Preço atual: R$ {product.current_price:.2f}\n"
        
        if product.target_price:
            alerts_text += f"   🎯 Preço alvo: R$ {product.target_price:.2f}\n"
        
        alerts_text += f"   📊 Status: {status_text}\n\n"
    
    await message.answer(
        alerts_text,
        reply_markup=get_alerts_keyboard()
    )
    
    await state.set_state(UserStates.viewing_alerts)


@router.message(Command("categories"))
async def cmd_categories(message: Message, state: FSMContext):
    """Handler para o comando /categories - mostra categorias"""
    user_id = message.from_user.id
    
    # Verificar inscrição
    is_member = await check_channel_membership(message.bot, user_id)
    if not is_member:
        await message.answer(
            "🔒 <b>Acesso necessário</b>\n\n"
            "Para ver as categorias, entre primeiro no nosso canal:",
            reply_markup=get_channel_verification_keyboard()
        )
        return
    
    # Buscar categorias
    categories = await product_service.get_categories()
    
    if not categories:
        await message.answer(
            "📂 <b>Categorias</b>\n\n"
            "Nenhuma categoria disponível no momento.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    await message.answer(
        "📂 <b>CATEGORIAS</b>\n\n"
        "Escolha uma categoria para ver os produtos:",
        reply_markup=get_categories_keyboard(categories)
    )
    
    await state.set_state(UserStates.selecting_category)


@router.message(F.text == "🔥 Ofertas Ativas")
async def show_active_offers(message: Message, state: FSMContext):
    """Mostra ofertas ativas quando usuário clica no botão"""
    await cmd_offers(message, state)


@router.message(F.text == "🔔 Meus Alertas")
async def show_my_alerts(message: Message, state: FSMContext):
    """Mostra alertas do usuário"""
    await cmd_alerts(message, state)


@router.message(F.text == "📂 Categorias")
async def show_categories(message: Message, state: FSMContext):
    """Mostra categorias"""
    await cmd_categories(message, state)


@router.message(F.text == "💬 Suporte")
async def show_support(message: Message):
    """Mostra informações de suporte"""
    support_text = (
        "💬 <b>Suporte Técnico</b>\n\n"
        "📧 <b>Email:</b> suporte@techoffers.com\n"
        "⏰ <b>Horário:</b> Seg-Sex, 9h às 18h\n"
        "📱 <b>Telegram:</b> @techoffers_suporte\n\n"
        "Descreva sua dúvida ou problema que nossa equipe responderá em breve!"
    )
    
    await message.answer(support_text, reply_markup=get_main_menu_keyboard())


@router.message(F.text == "ℹ️ Sobre")
async def show_about(message: Message):
    """Mostra informações sobre o bot"""
    about_text = (
        "🤖 <b>Tech Offers Bot</b>\n\n"
        "Sistema inteligente de ofertas tecnológicas.\n\n"
        "✅ <b>Funcionalidades:</b>\n"
        "• Ofertas exclusivas\n"
        "• Alertas de preço\n"
        "• Monitoramento automático\n"
        "• Links diretos para compra\n\n"
        "📊 <b>Estatísticas:</b>\n"
        "• +1000 produtos monitorados\n"
        "• Economia média de 40%\n"
        "• Atualização em tempo real"
    )
    
    await message.answer(about_text, reply_markup=get_main_menu_keyboard())


async def check_channel_membership(bot, user_id: int) -> bool:
    """
    Verifica se o usuário é membro do canal
    """
    try:
        channel_id = settings.CHANNEL_ID
        if not channel_id:
            logger.warning("CHANNEL_ID not configured, skipping membership check")
            return True
        
        # Verificar se o usuário é membro do canal
        chat_member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )
        
        is_member = chat_member.status in ['member', 'administrator', 'creator']
        
        # Atualizar status no banco
        async with db_manager.get_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.is_channel_member = is_member
                user.status = UserStatus.ACTIVE if is_member else UserStatus.PENDING
                user.last_interaction = datetime.utcnow()
                await session.commit()
        
        logger.info(f"User {user_id} channel membership: {is_member}")
        return is_member
        
    except Exception as e:
        logger.error(f"Error checking channel membership for user {user_id}: {e}")
        # Em caso de erro, permitir acesso temporário
        return True


async def process_product_deeplink(message: Message, product_code: str, state: FSMContext):
    """
    Processa deeplink de produto
    Quando usuário clica em "IR PARA OFERTA" no canal
    """
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} accessed product {product_code} via deeplink")
    
    # Verificar inscrição primeiro
    is_member = await check_channel_membership(message.bot, user_id)
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
    
    # Registrar origem do usuário
    await register_source_tracking(user_id, "channel_deeplink", product.id, product_code)
    
    # Registrar interação
    await register_interaction(user_id, "view_product", product.id)
    
    # Mostrar produto
    await show_product_details(message, product, state)


async def show_product_details(message: Message, product: Product, state: FSMContext):
    """
    Mostra detalhes do produto
    """
    # Verificar se usuário tem alerta ativo para este produto
    user_id = message.from_user.id
    has_alert = await alert_service.has_active_alert(user_id, product.id)
    
    # Preparar texto do produto
    product_text = f"🎧 <b>{product.name}</b>\n\n"
    
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
    
    # Enviar imagem se existir
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
    
    await state.set_state(UserStates.viewing_product)
    await state.update_data(current_product_id=product.id)


async def register_source_tracking(user_id: int, source_type: str, product_id: int, product_code: str):
    """
    Registra origem do usuário
    """
    async with db_manager.get_session() as session:
        from database.models import SourceTracking
        
        tracking = SourceTracking(
            user_id=user_id,
            source_type=source_type,
            source_id=str(product_id),
            product_code=product_code,
            tracking_data={
                "timestamp": datetime.utcnow().isoformat(),
                "source": "channel"
            }
        )
        
        session.add(tracking)
        await session.commit()
        
        logger.info(f"Source tracking registered for user {user_id}")


async def register_interaction(user_id: int, interaction_type: str, product_id: int = None, publication_id: int = None):
    """
    Registra interação do usuário
    """
    async with db_manager.get_session() as session:
        from database.models import UserInteraction
        
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
        
        logger.info(f"Interaction registered: user={user_id}, type={interaction_type}")
