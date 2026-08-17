"""
Handlers para gerenciamento de categorias
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional, List

from database.session import db_manager
from database.models import Category, Product
from bot.keyboards.admin_keyboards import get_admin_main_menu
from config import settings

router = Router()


class CategoryStates(StatesGroup):
    """Estados para gerenciamento de categorias"""
    waiting_name = State()
    waiting_emoji = State()
    waiting_description = State()
    editing_category = State()


@router.callback_query(F.data == "admin_list_categories")
async def list_categories(callback: CallbackQuery):
    """Lista todas as categorias"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Category)
            .where(Category.is_active == True)
            .order_by(Category.name)
        )
        categories = result.scalars().all()
    
    if not categories:
        await callback.message.answer(
            "📂 <b>Nenhuma categoria criada</b>\n\n"
            "Crie categorias para organizar seus produtos.",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com categorias
    keyboard = []
    for category in categories:
        # Contar produtos na categoria
        async with db_manager.get_session_no_commit() as session:
            from sqlalchemy import select, func
            
            product_count = await session.scalar(
                select(func.count(Product.id))
                .where(Product.category_id == category.id)
            )
        
        emoji = category.emoji or "📂"
        keyboard.append([InlineKeyboardButton(
            text=f"{emoji} {category.name} ({product_count or 0} produtos)",
            callback_data=f"view_category_{category.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_categories"
    )])
    
    await callback.message.edit_text(
        "📂 <b>CATEGORIAS</b>\n\n"
        f"Total: {len(categories)} categorias\n"
        "Clique em uma categoria para gerenciar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_category")
async def add_category(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de nova categoria"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await state.set_state(CategoryStates.waiting_name)
    await callback.message.answer(
        "📂 <b>NOVA CATEGORIA</b>\n\n"
        "Envie o nome da categoria:"
    )
    await callback.answer()


@router.message(CategoryStates.waiting_name)
async def process_category_name(message: Message, state: FSMContext):
    """Processa nome da categoria"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Nome muito curto. Envie novamente:")
        return
    
    await state.update_data(category_name=name)
    await state.set_state(CategoryStates.waiting_emoji)
    
    await message.answer(
        f"✅ Nome: <b>{name}</b>\n\n"
        "Agora envie um emoji para a categoria (ou envie /pular para pular):"
    )


@router.message(CategoryStates.waiting_emoji)
async def process_category_emoji(message: Message, state: FSMContext):
    """Processa emoji da categoria"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    emoji = message.text.strip()
    
    if emoji == '/pular':
        emoji = None
    elif len(emoji) > 10:
        await message.answer("❌ Emoji muito longo. Envie novamente ou /pular:")
        return
    
    await state.update_data(category_emoji=emoji)
    
    # Criar categoria
    data = await state.get_data()
    
    async with db_manager.get_session() as session:
        category = Category(
            name=data.get('category_name'),
            emoji=emoji,
            description=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(category)
        await session.commit()
        
        logger.info(f"Category created: {category.name}")
    
    await message.answer(
        f"✅ <b>CATEGORIA CRIADA!</b>\n\n"
        f"{emoji or '📂'} <b>Nome:</b> {category.name}\n\n"
        "A categoria está pronta para uso.",
        reply_markup=get_admin_main_menu()
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("view_category_"))
async def view_category(callback: CallbackQuery):
    """Visualiza categoria"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    category_id = int(callback.data.replace("view_category_", ""))
    
    async with db_manager.get_session_no_commit() as session:
        category = await session.get(Category, category_id)
        
        if not category:
            await callback.answer("❌ Categoria não encontrada", show_alert=True)
            return
        
        # Buscar produtos da categoria
        from sqlalchemy import select, func
        
        product_count = await session.scalar(
            select(func.count(Product.id))
            .where(Product.category_id == category_id)
        )
        
        products = await session.execute(
            select(Product)
            .where(Product.category_id == category_id)
            .limit(5)
        )
        products_list = products.scalars().all()
    
    # Texto da categoria
    category_text = (
        f"📂 <b>CATEGORIA</b>\n\n"
        f"{category.emoji or '📂'} <b>Nome:</b> {category.name}\n"
        f"📦 <b>Produtos:</b> {product_count or 0}\n"
        f"✅ <b>Ativa:</b> {'Sim' if category.is_active else 'Não'}\n"
    )
    
    if products_list:
        category_text += "\n<b>Produtos recentes:</b>\n"
        for product in products_list[:3]:
            category_text += f"• {product.name}\n"
    
    # Teclado de ações
    keyboard = [
        [InlineKeyboardButton(text="✏️ Editar Nome", callback_data=f"edit_category_{category.id}")],
        [InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"delete_category_{category.id}")],
        [InlineKeyboardButton(
            text="🔄 Desativar" if category.is_active else "✅ Ativar",
            callback_data=f"toggle_category_{category.id}"
        )],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_list_categories")]
    ]
    
    await callback.message.edit_text(
        category_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_category_"))
async def delete_category(callback: CallbackQuery):
    """Exclui categoria"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    category_id = int(callback.data.replace("delete_category_", ""))
    
    async with db_manager.get_session() as session:
        category = await session.get(Category, category_id)
        
        if category:
            # Verificar se há produtos
            from sqlalchemy import select, func
            
            product_count = await session.scalar(
                select(func.count(Product.id))
                .where(Product.category_id == category_id)
            )
            
            if product_count > 0:
                await callback.message.answer(
                    f"⚠️ <b>Não é possível excluir!</b>\n\n"
                    f"Existem {product_count} produtos nesta categoria.\n"
                    "Mova ou exclua os produtos primeiro.",
                    reply_markup=get_admin_main_menu()
                )
                await callback.answer()
                return
            
            category.is_active = False
            category.updated_at = datetime.utcnow()
            await session.commit()
            
            await callback.message.answer(
                "✅ <b>Categoria excluída!</b>",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_category_"))
async def toggle_category(callback: CallbackQuery):
    """Ativa/desativa categoria"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    category_id = int(callback.data.replace("toggle_category_", ""))
    
    async with db_manager.get_session() as session:
        category = await session.get(Category, category_id)
        
        if category:
            category.is_active = not category.is_active
            category.updated_at = datetime.utcnow()
            await session.commit()
            
            status = "ativada" if category.is_active else "desativada"
            await callback.message.answer(
                f"✅ Categoria <b>{status}</b>!",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()
