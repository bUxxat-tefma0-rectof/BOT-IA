"""
Handlers CRUD completos para administração
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional, List

from database.session import db_manager
from database.models import (
    Product, Category, Template, Publication, 
    Schedule, ButtonConfig, OfferStatus
)
from bot.keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_product_management_menu,
    get_confirmation_keyboard
)
from services.product_service import ProductService
from config import settings

router = Router()
product_service = ProductService()


class ProductEditStates(StatesGroup):
    """Estados para edição de produto"""
    waiting_product_id = State()
    editing_field = State()
    new_value = State()
    confirm_delete = State()
    search_query = State()


@router.callback_query(F.data == "admin_list_products")
async def list_products(callback: CallbackQuery):
    """Lista todos os produtos"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    products = await product_service.get_all_products(limit=20)
    
    if not products:
        await callback.message.answer(
            "📭 <b>Nenhum produto cadastrado</b>\n\n"
            "Use o botão 'Adicionar Produto' para criar um novo.",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com produtos
    keyboard = []
    for product in products:
        status_emoji = {
            OfferStatus.DRAFT: "📝",
            OfferStatus.PUBLISHED: "✅",
            OfferStatus.SCHEDULED: "📅",
            OfferStatus.EXPIRED: "⏰",
            OfferStatus.CANCELLED: "❌"
        }.get(product.status, "📦")
        
        keyboard.append([InlineKeyboardButton(
            text=f"{status_emoji} {product.name} ({product.product_code})",
            callback_data=f"view_product_admin_{product.id}"
        )])
    
    # Paginação
    if len(products) == 20:
        keyboard.append([InlineKeyboardButton(
            text="➡️ Próxima página",
            callback_data="admin_products_page_2"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_products"
    )])
    
    await callback.message.edit_text(
        "📦 <b>PRODUTOS CADASTRADOS</b>\n\n"
        f"Total: {len(products)} produtos\n"
        "Clique em um produto para gerenciar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_product_admin_"))
async def view_product_admin(callback: CallbackQuery):
    """Visualiza produto no painel admin"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("view_product_admin_", ""))
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Produto não encontrado", show_alert=True)
        return
    
    # Buscar estatísticas
    stats = await product_service.get_product_statistics(product_id)
    
    # Texto do produto
    product_text = (
        f"📦 <b>DETALHES DO PRODUTO</b>\n\n"
        f"🆔 <b>Código:</b> {product.product_code}\n"
        f"📝 <b>Nome:</b> {product.name}\n"
        f"💰 <b>Preço atual:</b> R$ {product.current_price:.2f}\n"
    )
    
    if product.original_price:
        product_text += f"💵 <b>Preço original:</b> R$ {product.original_price:.2f}\n"
    
    if product.discount_percentage:
        product_text += f"📊 <b>Desconto:</b> {product.discount_percentage:.1f}%\n"
    
    if product.description:
        product_text += f"\n📝 <b>Descrição:</b>\n{product.description}\n"
    
    product_text += (
        f"\n📈 <b>Estatísticas:</b>\n"
        f"• Visualizações: {stats.get('views_count', 0)}\n"
        f"• Cliques em comprar: {stats.get('buy_clicks', 0)}\n"
        f"• Alertas ativos: {stats.get('active_alerts', 0)}\n"
        f"• Taxa de conversão: {stats.get('conversion_rate', 0):.1f}%\n\n"
        f"📅 <b>Status:</b> {product.status.value}"
    )
    
    # Teclado de ações
    keyboard = [
        [InlineKeyboardButton(text="✏️ Editar", callback_data=f"edit_product_{product.id}")],
        [InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"delete_product_confirm_{product.id}")],
        [InlineKeyboardButton(text="📋 Duplicar", callback_data=f"duplicate_product_{product.id}")],
        [InlineKeyboardButton(text="📢 Publicar", callback_data=f"publish_product_{product.id}")],
        [
            InlineKeyboardButton(
                text="🔄 Ativar" if product.status != OfferStatus.PUBLISHED else "⏸️ Desativar",
                callback_data=f"toggle_product_{product.id}"
            )
        ],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_list_products")]
    ]
    
    await callback.message.edit_text(
        product_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_product_"))
async def edit_product_menu(callback: CallbackQuery, state: FSMContext):
    """Menu de edição de produto"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("edit_product_", ""))
    
    await state.update_data(editing_product_id=product_id)
    await state.set_state(ProductEditStates.editing_field)
    
    keyboard = [
        [InlineKeyboardButton(text="📝 Nome", callback_data=f"edit_field_name_{product_id}")],
        [InlineKeyboardButton(text="📄 Descrição", callback_data=f"edit_field_description_{product_id}")],
        [InlineKeyboardButton(text="💰 Preço Atual", callback_data=f"edit_field_current_price_{product_id}")],
        [InlineKeyboardButton(text="💵 Preço Original", callback_data=f"edit_field_original_price_{product_id}")],
        [InlineKeyboardButton(text="🎯 Preço Alvo", callback_data=f"edit_field_target_price_{product_id}")],
        [InlineKeyboardButton(text="🔗 Link Shopee", callback_data=f"edit_field_link_{product_id}")],
        [InlineKeyboardButton(text="🖼️ Imagem", callback_data=f"edit_field_image_{product_id}")],
        [InlineKeyboardButton(text="📂 Categoria", callback_data=f"edit_field_category_{product_id}")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data=f"view_product_admin_{product_id}")]
    ]
    
    await callback.message.edit_text(
        "✏️ <b>EDITAR PRODUTO</b>\n\n"
        "Selecione o campo que deseja editar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_"))
async def edit_product_field(callback: CallbackQuery, state: FSMContext):
    """Solicita novo valor para campo"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Extrair campo e ID do produto
    data = callback.data.replace("edit_field_", "")
    parts = data.rsplit("_", 1)
    field = parts[0]
    product_id = int(parts[1])
    
    field_names = {
        "name": "nome",
        "description": "descrição",
        "current_price": "preço atual",
        "original_price": "preço original",
        "target_price": "preço alvo",
        "link": "link da Shopee",
        "image": "URL da imagem",
        "category": "categoria"
    }
    
    await state.update_data(
        editing_product_id=product_id,
        editing_field=field
    )
    await state.set_state(ProductEditStates.new_value)
    
    await callback.message.answer(
        f"✏️ Envie o novo valor para <b>{field_names.get(field, field)}</b>:"
    )
    await callback.answer()


@router.message(ProductEditStates.new_value)
async def process_edit_value(message: Message, state: FSMContext):
    """Processa novo valor para campo"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    field = data.get('editing_field')
    
    if not product_id or not field:
        await message.answer("❌ Erro nos dados de edição.")
        await state.clear()
        return
    
    new_value = message.text.strip()
    
    # Validar e converter valor
    update_data = {}
    
    try:
        if field in ['current_price', 'original_price', 'target_price']:
            new_value = float(new_value.replace(',', '.'))
            update_data[field] = new_value
            
            # Recalcular desconto se necessário
            if field in ['current_price', 'original_price']:
                product = await product_service.get_product_by_id(product_id)
                if product:
                    if field == 'current_price':
                        original = product.original_price
                        current = new_value
                    else:
                        original = new_value
                        current = product.current_price
                    
                    if original and current:
                        update_data['discount_percentage'] = ((original - current) / original) * 100
        
        elif field == 'name':
            if len(new_value) < 3:
                await message.answer("❌ Nome muito curto. Envie novamente:")
                return
            update_data[field] = new_value
        
        elif field in ['link', 'image']:
            if not new_value.startswith('http'):
                await message.answer("❌ URL inválida. Envie novamente:")
                return
            update_data['shopee_link' if field == 'link' else 'image_url'] = new_value
        
        else:
            update_data[field] = new_value
        
        # Atualizar produto
        success = await product_service.update_product(product_id, update_data)
        
        if success:
            await message.answer(
                "✅ <b>Produto atualizado com sucesso!</b>",
                reply_markup=get_admin_main_menu()
            )
            logger.info(f"Product {product_id} updated by admin {message.from_user.id}")
        else:
            await message.answer(
                "❌ Erro ao atualizar produto.",
                reply_markup=get_admin_main_menu()
            )
        
    except ValueError:
        await message.answer("❌ Valor inválido. Envie novamente:")
        return
    
    await state.clear()


@router.callback_query(F.data.startswith("delete_product_confirm_"))
async def confirm_delete_product(callback: CallbackQuery):
    """Confirma exclusão de produto"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("delete_product_confirm_", ""))
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Produto não encontrado", show_alert=True)
        return
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ SIM, EXCLUIR",
                callback_data=f"delete_product_{product_id}"
            ),
            InlineKeyboardButton(
                text="❌ CANCELAR",
                callback_data=f"view_product_admin_{product_id}"
            )
        ]
    ]
    
    await callback.message.answer(
        f"⚠️ <b>CONFIRMAR EXCLUSÃO</b>\n\n"
        f"Tem certeza que deseja excluir o produto:\n"
        f"📦 {product.name} ({product.product_code})?\n\n"
        "Esta ação não pode ser desfeita!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_product_"))
async def delete_product(callback: CallbackQuery):
    """Exclui produto"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("delete_product_", ""))
    
    success = await product_service.delete_product(product_id)
    
    if success:
        await callback.message.answer(
            "✅ <b>Produto excluído com sucesso!</b>",
            reply_markup=get_admin_main_menu()
        )
        logger.info(f"Product {product_id} deleted by admin {callback.from_user.id}")
    else:
        await callback.message.answer(
            "❌ Erro ao excluir produto.",
            reply_markup=get_admin_main_menu()
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("duplicate_product_"))
async def duplicate_product(callback: CallbackQuery):
    """Duplica produto"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("duplicate_product_", ""))
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Produto não encontrado", show_alert=True)
        return
    
    # Criar cópia do produto
    import random
    new_product_data = {
        'name': f"{product.name} (Cópia)",
        'description': product.description,
        'original_price': product.original_price,
        'current_price': product.current_price,
        'target_price': product.target_price,
        'discount_percentage': product.discount_percentage,
        'shopee_link': product.shopee_link,
        'image_url': product.image_url,
        'category_id': product.category_id
    }
    
    new_product = await product_service.create_product(new_product_data)
    
    if new_product:
        await callback.message.answer(
            f"✅ <b>Produto duplicado com sucesso!</b>\n\n"
            f"Original: {product.product_code}\n"
            f"Cópia: {new_product.product_code}",
            reply_markup=get_admin_main_menu()
        )
    else:
        await callback.message.answer(
            "❌ Erro ao duplicar produto.",
            reply_markup=get_admin_main_menu()
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_product_"))
async def toggle_product_status(callback: CallbackQuery):
    """Ativa/desativa produto"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("toggle_product_", ""))
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Produto não encontrado", show_alert=True)
        return
    
    # Alternar status
    if product.status == OfferStatus.PUBLISHED:
        new_status = OfferStatus.CANCELLED
        status_text = "desativado"
    else:
        new_status = OfferStatus.PUBLISHED
        status_text = "ativado"
    
    success = await product_service.update_product(product_id, {'status': new_status})
    
    if success:
        await callback.message.answer(
            f"✅ Produto <b>{status_text}</b> com sucesso!",
            reply_markup=get_admin_main_menu()
        )
    else:
        await callback.message.answer(
            "❌ Erro ao alterar status.",
            reply_markup=get_admin_main_menu()
        )
    
    await callback.answer()


@router.callback_query(F.data == "admin_search_product")
async def search_product_prompt(callback: CallbackQuery, state: FSMContext):
    """Solicita termo de busca"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await state.set_state(ProductEditStates.search_query)
    await callback.message.answer(
        "🔍 <b>PESQUISAR PRODUTO</b>\n\n"
        "Envie o termo de busca:"
    )
    await callback.answer()


@router.message(ProductEditStates.search_query)
async def search_products(message: Message, state: FSMContext):
    """Busca produtos"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer("❌ Termo muito curto. Envie novamente:")
        return
    
    products = await product_service.search_products(query)
    
    if not products:
        await message.answer(
            "📭 <b>Nenhum produto encontrado</b>",
            reply_markup=get_admin_main_menu()
        )
        await state.clear()
        return
    
    # Criar teclado com resultados
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            text=f"📦 {product.name} ({product.product_code})",
            callback_data=f"view_product_admin_{product.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_products"
    )])
    
    await message.answer(
        f"🔍 <b>RESULTADOS DA BUSCA</b>\n\n"
        f"Encontrados {len(products)} produtos:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.clear()
