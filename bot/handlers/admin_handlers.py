"""
Handlers administrativos do bot
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime, timedelta
from typing import Optional, List
import json

from database.session import db_manager
from database.models import (
    User, Product, Category, Alert, Template, 
    Publication, Schedule, ButtonConfig, AdminLog,
    OfferStatus, UserStatus
)
from bot.keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_product_management_menu,
    get_publication_menu,
    get_alerts_management_menu,
    get_statistics_menu,
    get_schedule_menu,
    get_template_menu,
    get_category_menu,
    get_confirmation_keyboard
)
from services.product_service import ProductService
from services.publication_service import PublicationService
from services.alert_service import AlertService
from services.analytics_service import AnalyticsService
from config import settings

router = Router()
product_service = ProductService()
publication_service = PublicationService()
alert_service = AlertService()
analytics_service = AnalyticsService()


class AdminStates(StatesGroup):
    """Estados administrativos"""
    # Produto
    adding_product = State()
    editing_product = State()
    product_name = State()
    product_description = State()
    product_price = State()
    product_original_price = State()
    product_link = State()
    product_category = State()
    product_image = State()
    
    # Publicação
    creating_publication = State()
    selecting_product_publication = State()
    scheduling_publication = State()
    
    # Template
    creating_template = State()
    template_name = State()
    template_text = State()
    
    # Categoria
    adding_category = State()
    category_name = State()
    
    # Agendamento
    creating_schedule = State()
    schedule_name = State()
    schedule_time = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """
    Handler para o comando /admin
    Acesso restrito ao administrador
    """
    user_id = message.from_user.id
    
    # Verificar se é admin
    if user_id != settings.ADMIN_ID:
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await message.answer(
            "⛔ <b>Acesso negado</b>\n\n"
            "Você não tem permissão para acessar o painel administrativo."
        )
        return
    
    logger.info(f"Admin {user_id} accessed admin panel")
    
    # Registrar log
    await register_admin_log(user_id, "access_admin_panel")
    
    await message.answer(
        "⚙️ <b>PAINEL ADMINISTRATIVO</b>\n\n"
        f"👋 Bem-vindo, {message.from_user.first_name}!\n"
        "Selecione uma opção abaixo:",
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "admin_main")
async def admin_main_menu(callback: CallbackQuery, state: FSMContext):
    """Retorna ao menu principal admin"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⚙️ <b>PAINEL ADMINISTRATIVO</b>\n\n"
        "Selecione uma opção abaixo:",
        reply_markup=get_admin_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_products")
async def admin_products_menu(callback: CallbackQuery):
    """Menu de gerenciamento de produtos"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📦 <b>GERENCIAMENTO DE PRODUTOS</b>\n\n"
        "Selecione uma ação:",
        reply_markup=get_product_management_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    """Inicia processo de adição de produto"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ <b>NOVO PRODUTO</b>\n\n"
        "Vamos adicionar um novo produto.\n"
        "Envie o nome do produto:"
    )
    
    await state.set_state(AdminStates.product_name)
    await callback.answer()


@router.message(AdminStates.product_name)
async def process_product_name(message: Message, state: FSMContext):
    """Processa nome do produto"""
    product_name = message.text.strip()
    
    if len(product_name) < 3:
        await message.answer(
            "❌ Nome muito curto. Envie um nome válido com pelo menos 3 caracteres:"
        )
        return
    
    await state.update_data(name=product_name)
    
    await message.answer(
        f"✅ Nome: <b>{product_name}</b>\n\n"
        "Agora envie a descrição do produto:"
    )
    
    await state.set_state(AdminStates.product_description)


@router.message(AdminStates.product_description)
async def process_product_description(message: Message, state: FSMContext):
    """Processa descrição do produto"""
    description = message.text.strip()
    
    await state.update_data(description=description)
    
    await message.answer(
        "✅ Descrição salva!\n\n"
        "Agora envie o preço atual do produto (apenas números):"
    )
    
    await state.set_state(AdminStates.product_price)


@router.message(AdminStates.product_price)
async def process_product_price(message: Message, state: FSMContext):
    """Processa preço do produto"""
    try:
        price = float(message.text.replace(',', '.').strip())
        
        if price <= 0:
            raise ValueError("Price must be positive")
        
        await state.update_data(current_price=price)
        
        await message.answer(
            f"✅ Preço atual: R$ {price:.2f}\n\n"
            "Agora envie o preço original/anterior (ou envie 0 se não houver):"
        )
        
        await state.set_state(AdminStates.product_original_price)
        
    except ValueError:
        await message.answer(
            "❌ Preço inválido. Envie apenas números (ex: 79.90):"
        )


@router.message(AdminStates.product_original_price)
async def process_product_original_price(message: Message, state: FSMContext):
    """Processa preço original do produto"""
    try:
        original_price = float(message.text.replace(',', '.').strip())
        
        if original_price < 0:
            raise ValueError("Price must be non-negative")
        
        data = await state.get_data()
        current_price = data.get('current_price', 0)
        
        # Calcular desconto
        discount = 0
        if original_price > 0 and current_price > 0:
            discount = ((original_price - current_price) / original_price) * 100
        
        await state.update_data(
            original_price=original_price,
            discount_percentage=discount
        )
        
        if discount > 0:
            await message.answer(
                f"✅ Preço original: R$ {original_price:.2f}\n"
                f"📊 Desconto calculado: {discount:.1f}%\n\n"
                "Agora envie o link da Shopee:"
            )
        else:
            await message.answer(
                f"✅ Preço original: R$ {original_price:.2f}\n\n"
                "Agora envie o link da Shopee:"
            )
        
        await state.set_state(AdminStates.product_link)
        
    except ValueError:
        await message.answer(
            "❌ Preço inválido. Envie apenas números (ex: 149.90):"
        )


@router.message(AdminStates.product_link)
async def process_product_link(message: Message, state: FSMContext):
    """Processa link do produto"""
    link = message.text.strip()
    
    if not link.startswith('http'):
        await message.answer(
            "❌ Link inválido. Envie um link válido da Shopee (ex: https://shopee.com.br/...):"
        )
        return
    
    await state.update_data(shopee_link=link)
    
    # Buscar categorias para seleção
    categories = await product_service.get_categories()
    
    if categories:
        # Criar teclado com categorias
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(
                text=f"{cat.emoji or '📂'} {cat.name}",
                callback_data=f"set_category_{cat.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            text="➕ Nova categoria",
            callback_data="new_category"
        )])
        
        await message.answer(
            "✅ Link salvo!\n\n"
            "Agora selecione a categoria do produto:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        await state.set_state(AdminStates.product_category)
    else:
        # Sem categorias, pular
        await state.update_data(category_id=None)
        
        await message.answer(
            "✅ Link salvo!\n\n"
            "Não há categorias cadastradas. O produto será criado sem categoria.\n"
            "Envie a URL da imagem do produto:"
        )
        
        await state.set_state(AdminStates.product_image)


@router.callback_query(F.data.startswith("set_category_"))
async def set_product_category(callback: CallbackQuery, state: FSMContext):
    """Define categoria do produto"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    category_id = int(callback.data.replace("set_category_", ""))
    
    await state.update_data(category_id=category_id)
    
    await callback.message.answer(
        "✅ Categoria selecionada!\n\n"
        "Agora envie a URL da imagem do produto:"
    )
    
    await state.set_state(AdminStates.product_image)
    await callback.answer()


@router.message(AdminStates.product_image)
async def process_product_image(message: Message, state: FSMContext):
    """Processa imagem do produto e finaliza cadastro"""
    image_url = message.text.strip() if message.text else None
    
    if image_url and not image_url.startswith('http'):
        await message.answer(
            "❌ URL inválida. Envie uma URL válida ou envie /skip para pular:"
        )
        return
    
    data = await state.get_data()
    
    # Gerar código único do produto
    import random
    product_code = f"#{random.randint(100, 999)}"
    
    # Criar produto
    try:
        async with db_manager.get_session() as session:
            product = Product(
                product_code=product_code,
                name=data.get('name'),
                description=data.get('description'),
                current_price=data.get('current_price'),
                original_price=data.get('original_price'),
                discount_percentage=data.get('discount_percentage'),
                shopee_link=data.get('shopee_link'),
                image_url=image_url,
                category_id=data.get('category_id'),
                status=OfferStatus.DRAFT,
                created_at=datetime.utcnow()
            )
            
            session.add(product)
            await session.commit()
            
            logger.info(f"Product created: {product.product_code} - {product.name}")
            
            # Registrar log
            await register_admin_log(message.from_user.id, "create_product", f"Code: {product_code}")
            
            await message.answer(
                f"✅ <b>PRODUTO CRIADO COM SUCESSO!</b>\n\n"
                f"📦 <b>Produto:</b> {product.name}\n"
                f"🆔 <b>Código:</b> {product.product_code}\n"
                f"💰 <b>Preço:</b> R$ {product.current_price:.2f}\n"
                f"📊 <b>Desconto:</b> {product.discount_percentage:.1f}%\n\n"
                "O produto foi adicionado como rascunho.\n"
                "Você pode publicá-lo pelo menu de publicações.",
                reply_markup=get_admin_main_menu()
            )
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        await message.answer(
            "❌ Erro ao criar produto. Tente novamente mais tarde.",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin_publications")
async def admin_publications_menu(callback: CallbackQuery):
    """Menu de publicações"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>GERENCIAMENTO DE PUBLICAÇÕES</b>\n\n"
        "Selecione uma ação:",
        reply_markup=get_publication_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_publish_product")
async def admin_publish_product(callback: CallbackQuery, state: FSMContext):
    """Inicia publicação de produto"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Buscar produtos rascunho
    products = await product_service.get_draft_products()
    
    if not products:
        await callback.message.answer(
            "📭 Não há produtos em rascunho para publicar.\n"
            "Crie um produto primeiro!",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com produtos
    keyboard = []
    for product in products[:10]:
        keyboard.append([InlineKeyboardButton(
            text=f"📦 {product.name} ({product.product_code})",
            callback_data=f"publish_product_{product.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_publications"
    )])
    
    await callback.message.answer(
        "📢 <b>PUBLICAR PRODUTO</b>\n\n"
        "Selecione o produto que deseja publicar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("publish_product_"))
async def publish_product_to_channel(callback: CallbackQuery):
    """Publica produto no canal"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("publish_product_", ""))
    
    # Publicar no canal
    try:
        publication = await publication_service.publish_product_to_channel(
            bot=callback.bot,
            product_id=product_id
        )
        
        if publication:
            await callback.message.answer(
                f"✅ <b>PRODUTO PUBLICADO!</b>\n\n"
                f"📦 Produto: {publication.product.name}\n"
                f"🆔 Código: {publication.product.product_code}\n"
                f"📢 Mensagem: {publication.channel_message_id}\n\n"
                "O produto foi publicado no canal com sucesso!",
                reply_markup=get_admin_main_menu()
            )
            
            # Registrar log
            await register_admin_log(
                callback.from_user.id,
                "publish_product",
                f"Product ID: {product_id}"
            )
        else:
            await callback.message.answer(
                "❌ Erro ao publicar produto.",
                reply_markup=get_admin_main_menu()
            )
    
    except Exception as e:
        logger.error(f"Error publishing product: {e}")
        await callback.message.answer(
            f"❌ Erro: {str(e)}",
            reply_markup=get_admin_main_menu()
        )
    
    await callback.answer()


@router.callback_query(F.data == "admin_alerts")
async def admin_alerts_menu(callback: CallbackQuery):
    """Menu de alertas"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Buscar estatísticas de alertas
    stats = await alert_service.get_alert_statistics()
    
    await callback.message.edit_text(
        "🔔 <b>GERENCIAMENTO DE ALERTAS</b>\n\n"
        f"📊 <b>Estatísticas:</b>\n"
        f"• Total de alertas ativos: {stats['active_alerts']}\n"
        f"• Produtos monitorados: {stats['monitored_products']}\n"
        f"• Usuários com alertas: {stats['users_with_alerts']}\n\n"
        "Selecione uma ação:",
        reply_markup=get_alerts_management_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_statistics")
async def admin_statistics_menu(callback: CallbackQuery):
    """Menu de estatísticas"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Buscar estatísticas gerais
    stats = await analytics_service.get_general_statistics()
    
    stats_text = (
        "📊 <b>ESTATÍSTICAS GERAIS</b>\n\n"
        f"👥 <b>Usuários:</b>\n"
        f"• Total: {stats['total_users']}\n"
        f"• Ativos: {stats['active_users']}\n\n"
        f"📦 <b>Produtos:</b>\n"
        f"• Total: {stats['total_products']}\n"
        f"• Ativos: {stats['active_products']}\n"
        f"• Publicados: {stats['published_products']}\n\n"
        f"🔄 <b>Interações:</b>\n"
        f"• Visualizações: {stats['total_views']}\n"
        f"• Cliques em comprar: {stats['buy_clicks']}\n"
        f"• Alertas ativados: {stats['alert_activations']}\n\n"
        f"📈 <b>Performance:</b>\n"
        f"• Produto mais visto: {stats['most_viewed_product']}\n"
        f"• Categoria mais acessada: {stats['most_accessed_category']}"
    )
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=get_statistics_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_schedules")
async def admin_schedules_menu(callback: CallbackQuery):
    """Menu de agendamentos"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📅 <b>AGENDAMENTOS</b>\n\n"
        "Configure publicações automáticas:",
        reply_markup=get_schedule_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_templates")
async def admin_templates_menu(callback: CallbackQuery):
    """Menu de templates"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 <b>TEMPLATES DE PUBLICAÇÃO</b>\n\n"
        "Gerencie templates reutilizáveis:",
        reply_markup=get_template_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_categories")
async def admin_categories_menu(callback: CallbackQuery):
    """Menu de categorias"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📂 <b>CATEGORIAS</b>\n\n"
        "Gerencie categorias de produtos:",
        reply_markup=get_category_menu()
    )
    await callback.answer()


async def check_admin(user_id: int) -> bool:
    """Verifica se usuário é admin"""
    return user_id == settings.ADMIN_ID


async def register_admin_log(admin_id: int, action: str, details: str = None):
    """Registra log administrativo"""
    async with db_manager.get_session() as session:
        from database.models import AdminLog
        
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            details=details,
            created_at=datetime.utcnow()
        )
        
        session.add(log)
        await session.commit()
