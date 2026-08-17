"""
Handlers para gerenciamento de templates
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional, List

from database.session import db_manager
from database.models import Template, Product, Publication
from bot.keyboards.admin_keyboards import get_admin_main_menu
from config import settings

router = Router()


class TemplateStates(StatesGroup):
    """Estados para criação/edição de templates"""
    waiting_name = State()
    waiting_text = State()
    waiting_buttons = State()
    editing_template = State()


@router.callback_query(F.data == "admin_list_templates")
async def list_templates(callback: CallbackQuery):
    """Lista todos os templates"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Template)
            .order_by(Template.created_at.desc())
        )
        templates = result.scalars().all()
    
    if not templates:
        await callback.message.answer(
            "📝 <b>Nenhum template criado</b>\n\n"
            "Crie um template para padronizar suas publicações.",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com templates
    keyboard = []
    for template in templates:
        keyboard.append([InlineKeyboardButton(
            text=f"📝 {template.name}",
            callback_data=f"view_template_{template.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_templates"
    )])
    
    await callback.message.edit_text(
        "📝 <b>TEMPLATES DISPONÍVEIS</b>\n\n"
        f"Total: {len(templates)} templates\n"
        "Clique em um template para gerenciar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_new_template")
async def new_template(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de novo template"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await state.set_state(TemplateStates.waiting_name)
    await callback.message.answer(
        "📝 <b>NOVO TEMPLATE</b>\n\n"
        "Envie o nome do template:"
    )
    await callback.answer()


@router.message(TemplateStates.waiting_name)
async def process_template_name(message: Message, state: FSMContext):
    """Processa nome do template"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    name = message.text.strip()
    
    if len(name) < 3:
        await message.answer("❌ Nome muito curto. Envie novamente:")
        return
    
    await state.update_data(template_name=name)
    await state.set_state(TemplateStates.waiting_text)
    
    await message.answer(
        f"✅ Nome: <b>{name}</b>\n\n"
        "Agora envie o texto do template.\n\n"
        "<b>Variáveis disponíveis:</b>\n"
        "• {product_name} - Nome do produto\n"
        "• {original_price} - Preço original\n"
        "• {current_price} - Preço atual\n"
        "• {discount} - Percentual de desconto\n"
        "• {description} - Descrição\n"
        "• {product_code} - Código do produto"
    )


@router.message(TemplateStates.waiting_text)
async def process_template_text(message: Message, state: FSMContext):
    """Processa texto do template"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    template_text = message.text
    
    if len(template_text) > 4000:
        await message.answer("❌ Texto muito longo (máximo 4000 caracteres). Envie novamente:")
        return
    
    await state.update_data(template_text=template_text)
    
    # Criar template
    data = await state.get_data()
    
    async with db_manager.get_session() as session:
        template = Template(
            name=data.get('template_name'),
            template_text=template_text,
            template_buttons=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        await session.commit()
        
        logger.info(f"Template created: {template.name}")
    
    await message.answer(
        f"✅ <b>TEMPLATE CRIADO!</b>\n\n"
        f"📝 Nome: {template.name}\n"
        f"📄 Texto configurado\n\n"
        "O template está pronto para uso nas publicações.",
        reply_markup=get_admin_main_menu()
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("view_template_"))
async def view_template(callback: CallbackQuery):
    """Visualiza template"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    template_id = int(callback.data.replace("view_template_", ""))
    
    async with db_manager.get_session_no_commit() as session:
        template = await session.get(Template, template_id)
    
    if not template:
        await callback.answer("❌ Template não encontrado", show_alert=True)
        return
    
    # Texto do template
    template_text = (
        f"📝 <b>TEMPLATE</b>\n\n"
        f"📄 <b>Nome:</b> {template.name}\n"
        f"📝 <b>Descrição:</b> {template.description or 'N/A'}\n"
        f"✅ <b>Ativo:</b> {'Sim' if template.is_active else 'Não'}\n\n"
        f"<b>Texto do template:</b>\n{template.template_text[:500]}..."
    )
    
    # Teclado de ações
    keyboard = [
        [InlineKeyboardButton(text="✏️ Editar", callback_data=f"edit_template_{template.id}")],
        [InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"delete_template_{template.id}")],
        [InlineKeyboardButton(
            text="🔄 Desativar" if template.is_active else "✅ Ativar",
            callback_data=f"toggle_template_{template.id}"
        )],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_list_templates")]
    ]
    
    await callback.message.edit_text(
        template_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_template_"))
async def delete_template(callback: CallbackQuery):
    """Exclui template"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    template_id = int(callback.data.replace("delete_template_", ""))
    
    async with db_manager.get_session() as session:
        template = await session.get(Template, template_id)
        
        if template:
            await session.delete(template)
            await session.commit()
            
            await callback.message.answer(
                "✅ <b>Template excluído!</b>",
                reply_markup=get_admin_main_menu()
            )
        else:
            await callback.message.answer(
                "❌ Template não encontrado.",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_template_"))
async def toggle_template(callback: CallbackQuery):
    """Ativa/desativa template"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    template_id = int(callback.data.replace("toggle_template_", ""))
    
    async with db_manager.get_session() as session:
        template = await session.get(Template, template_id)
        
        if template:
            template.is_active = not template.is_active
            template.updated_at = datetime.utcnow()
            await session.commit()
            
            status = "ativado" if template.is_active else "desativado"
            await callback.message.answer(
                f"✅ Template <b>{status}</b>!",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()


@router.callback_query(F.data == "admin_offer_template")
async def create_offer_template(callback: CallbackQuery):
    """Cria template de oferta padrão"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Template de oferta padrão
    template_text = """🔥 OFERTA TECNOLÓGICA

📦 {product_name}

💰 De: R$ {original_price}
🔥 Por: R$ {current_price}
📊 Desconto: {discount}%

📝 {description}

🆔 Código: {product_code}"""
    
    async with db_manager.get_session() as session:
        template = Template(
            name="Template de Oferta Padrão",
            description="Template padrão para ofertas",
            template_text=template_text,
            template_buttons=[
                {"text": "⚪ ATIVAR PROMOÇÃO", "action": "activate_promotion"},
                {"text": "🛒 IR PARA OFERTA", "action": "go_to_offer"},
                {"text": "💬 SUPORTE", "action": "support"}
            ],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        await session.commit()
    
    await callback.message.answer(
        "✅ <b>Template de oferta criado!</b>",
        reply_markup=get_admin_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_flash_template")
async def create_flash_template(callback: CallbackQuery):
    """Cria template de oferta relâmpago"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Template de oferta relâmpago
    template_text = """🚨 OFERTA RELÂMPAGO ⚡

📦 {product_name}

💥 De R$ {original_price}
⚡ Por apenas R$ {current_price}

🔥 {discount}% DE DESCONTO!

⏰ TEMPO LIMITADO!

🛒 {shopee_link}"""
    
    async with db_manager.get_session() as session:
        template = Template(
            name="Template de Oferta Relâmpago",
            description="Template para ofertas relâmpago",
            template_text=template_text,
            template_buttons=[
                {"text": "⚡ COMPRAR AGORA", "action": "buy_now"},
                {"text": "🔔 ATIVAR ALERTA", "action": "activate_alert"}
            ],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        await session.commit()
    
    await callback.message.answer(
        "✅ <b>Template de oferta relâmpago criado!</b>",
        reply_markup=get_admin_main_menu()
    )
    await callback.answer()
