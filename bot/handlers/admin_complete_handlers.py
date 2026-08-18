"""
Handlers administrativos completos
Inclui CRUD de categorias, templates, botões e agendamentos
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
    User, Product, Category, Template, 
    ButtonConfig, Schedule, AdminLog,
    OfferStatus
)
from bot.keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_category_menu,
    get_template_menu,
    get_confirmation_keyboard
)
from config import settings

router = Router()


class AdminStates(StatesGroup):
    """Estados administrativos"""
    # Categorias
    adding_category_name = State()
    editing_category = State()
    
    # Templates
    adding_template_name = State()
    adding_template_text = State()
    adding_template_buttons = State()
    
    # Botões
    adding_button_name = State()
    adding_button_text = State()
    adding_button_action = State()
    adding_button_url = State()
    adding_button_callback = State()
    
    # Agendamentos
    adding_schedule_name = State()
    adding_schedule_time = State()
    adding_schedule_days = State()


# ==================== CATEGORIAS ====================

@router.callback_query(F.data == "admin_add_category")
async def admin_add_category(callback: CallbackQuery, state: FSMContext):
    """Inicia adição de categoria"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.answer(
        "📂 <b>NOVA CATEGORIA</b>\n\n"
        "Envie o nome da categoria:"
    )
    
    await state.set_state(AdminStates.adding_category_name)
    await callback.answer()


@router.message(AdminStates.adding_category_name)
async def process_category_name(message: Message, state: FSMContext):
    """Processa nome da categoria"""
    category_name = message.text.strip()
    
    if len(category_name) < 2:
        await message.answer("❌ Nome muito curto. Envie novamente:")
        return
    
    # Criar categoria
    async with db_manager.get_session() as session:
        category = Category(
            name=category_name,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(category)
        await session.commit()
        
        # Registrar log
        await register_admin_log(message.from_user.id, "create_category", category_name)
        
        await message.answer(
            f"✅ <b>Categoria criada!</b>\n\n"
            f"📂 Nome: {category_name}\n"
            f"🆔 ID: {category.id}",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin_list_categories")
async def admin_list_categories(callback: CallbackQuery):
    """Lista categorias"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Category).order_by(Category.name)
        )
        categories = result.scalars().all()
        
        if not categories:
            await callback.message.answer("📭 Nenhuma categoria cadastrada.")
            await callback.answer()
            return
        
        categories_text = "📂 <b>CATEGORIAS CADASTRADAS</b>\n\n"
        
        for i, cat in enumerate(categories, 1):
            categories_text += f"{i}. {cat.emoji or '📂'} <b>{cat.name}</b> (ID: {cat.id})\n"
        
        categories_text += "\nUse /admin para voltar ao painel."
        
        await callback.message.answer(categories_text)
        await callback.answer()


# ==================== TEMPLATES ====================

@router.callback_query(F.data == "admin_new_template")
async def admin_new_template(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de template"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 <b>NOVO TEMPLATE</b>\n\n"
        "Envie o nome do template:"
    )
    
    await state.set_state(AdminStates.adding_template_name)
    await callback.answer()


@router.message(AdminStates.adding_template_name)
async def process_template_name(message: Message, state: FSMContext):
    """Processa nome do template"""
    template_name = message.text.strip()
    
    await state.update_data(template_name=template_name)
    
    await message.answer(
        f"✅ Nome: <b>{template_name}</b>\n\n"
        "Agora envie o texto do template.\n"
        "Use {name}, {price}, {original_price}, {discount} como variáveis:"
    )
    
    await state.set_state(AdminStates.adding_template_text)


@router.message(AdminStates.adding_template_text)
async def process_template_text(message: Message, state: FSMContext):
    """Processa texto do template"""
    template_text = message.text.strip()
    
    await state.update_data(template_text=template_text)
    
    # Criar template
    data = await state.get_data()
    
    async with db_manager.get_session() as session:
        template = Template(
            name=data['template_name'],
            template_text=template_text,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        await session.commit()
        
        await register_admin_log(message.from_user.id, "create_template", template.name)
        
        await message.answer(
            f"✅ <b>Template criado!</b>\n\n"
            f"📝 Nome: {template.name}\n"
            f"🆔 ID: {template.id}",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


@router.callback_query(F.data == "admin_list_templates")
async def admin_list_templates(callback: CallbackQuery):
    """Lista templates"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Template).where(Template.is_active == True)
        )
        templates = result.scalars().all()
        
        if not templates:
            await callback.message.answer("📭 Nenhum template cadastrado.")
            await callback.answer()
            return
        
        templates_text = "📝 <b>TEMPLATES DISPONÍVEIS</b>\n\n"
        
        for i, template in enumerate(templates, 1):
            templates_text += f"{i}. <b>{template.name}</b> (ID: {template.id})\n"
        
        await callback.message.answer(templates_text)
        await callback.answer()


# ==================== BOTÕES CONFIGURÁVEIS ====================

@router.callback_query(F.data == "admin_new_button")
async def admin_new_button(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de botão configurável"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.answer(
        "🔘 <b>NOVO BOTÃO</b>\n\n"
        "Envie o nome do botão (para identificação):"
    )
    
    await state.set_state(AdminStates.adding_button_name)
    await callback.answer()


@router.message(AdminStates.adding_button_name)
async def process_button_name(message: Message, state: FSMContext):
    """Processa nome do botão"""
    button_name = message.text.strip()
    
    await state.update_data(button_name=button_name)
    
    await message.answer(
        f"✅ Nome: <b>{button_name}</b>\n\n"
        "Agora envie o texto que aparecerá no botão:\n"
        "(Ex: 🛒 COMPRAR AGORA)"
    )
    
    await state.set_state(AdminStates.adding_button_text)


@router.message(AdminStates.adding_button_text)
async def process_button_text(message: Message, state: FSMContext):
    """Processa texto do botão"""
    button_text = message.text.strip()
    
    await state.update_data(button_text=button_text)
    
    # Mostrar opções de ação
    actions_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Alerta", callback_data="btn_action_alert")],
        [InlineKeyboardButton(text="🛒 Compra", callback_data="btn_action_buy")],
        [InlineKeyboardButton(text="💬 Suporte", callback_data="btn_action_support")],
        [InlineKeyboardButton(text="🔗 URL", callback_data="btn_action_url")],
        [InlineKeyboardButton(text="📞 Callback", callback_data="btn_action_callback")]
    ])
    
    await message.answer(
        f"✅ Texto: <b>{button_text}</b>\n\n"
        "Escolha o tipo de ação:",
        reply_markup=actions_keyboard
    )
    
    await state.set_state(AdminStates.adding_button_action)


@router.callback_query(F.data.startswith("btn_action_"))
async def process_button_action(callback: CallbackQuery, state: FSMContext):
    """Processa ação do botão"""
    action_type = callback.data.replace("btn_action_", "")
    
    await state.update_data(action_type=action_type)
    
    if action_type == "url":
        await callback.message.answer("Envie a URL do botão:")
        await state.set_state(AdminStates.adding_button_url)
    elif action_type == "callback":
        await callback.message.answer("Envie o callback_data do botão:")
        await state.set_state(AdminStates.adding_button_callback)
    else:
        # Criar botão com ação direta
        await create_button(callback.message, state)
    
    await callback.answer()


@router.message(AdminStates.adding_button_url)
async def process_button_url(message: Message, state: FSMContext):
    """Processa URL do botão"""
    url = message.text.strip()
    
    if not url.startswith('http'):
        await message.answer("❌ URL inválida. Envie novamente:")
        return
    
    await state.update_data(url=url)
    
    await create_button(message, state)


@router.message(AdminStates.adding_button_callback)
async def process_button_callback(message: Message, state: FSMContext):
    """Processa callback do botão"""
    callback_data = message.text.strip()
    
    await state.update_data(callback_data=callback_data)
    
    await create_button(message, state)


async def create_button(message: Message, state: FSMContext):
    """Cria botão configurável"""
    data = await state.get_data()
    
    async with db_manager.get_session() as session:
        button = ButtonConfig(
            name=data['button_name'],
            text=data['button_text'],
            action_type=data['action_type'],
            url=data.get('url'),
            callback_data=data.get('callback_data'),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(button)
        await session.commit()
        
        await register_admin_log(message.from_user.id, "create_button", button.name)
        
        await message.answer(
            f"✅ <b>Botão criado!</b>\n\n"
            f"🔘 Nome: {button.name}\n"
            f"📝 Texto: {button.text}\n"
            f"🎯 Ação: {button.action_type}",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


# ==================== AGENDAMENTOS ====================

@router.callback_query(F.data == "admin_new_schedule")
async def admin_new_schedule(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de agendamento"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await callback.message.answer(
        "📅 <b>NOVO AGENDAMENTO</b>\n\n"
        "Envie o nome do agendamento:"
    )
    
    await state.set_state(AdminStates.adding_schedule_name)
    await callback.answer()


@router.message(AdminStates.adding_schedule_name)
async def process_schedule_name(message: Message, state: FSMContext):
    """Processa nome do agendamento"""
    schedule_name = message.text.strip()
    
    await state.update_data(schedule_name=schedule_name)
    
    await message.answer(
        f"✅ Nome: <b>{schedule_name}</b>\n\n"
        "Agora envie os horários (separados por vírgula):\n"
        "Ex: 09:00, 12:00, 15:00, 18:00"
    )
    
    await state.set_state(AdminStates.adding_schedule_time)


@router.message(AdminStates.adding_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext):
    """Processa horários do agendamento"""
    times_text = message.text.strip()
    times = [t.strip() for t in times_text.split(',')]
    
    # Validar horários
    import re
    time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    valid_times = []
    
    for time_str in times:
        if re.match(time_pattern, time_str):
            valid_times.append(time_str)
    
    if not valid_times:
        await message.answer("❌ Nenhum horário válido. Envie novamente:")
        return
    
    await state.update_data(times=valid_times)
    
    # Criar agendamento
    data = await state.get_data()
    
    async with db_manager.get_session() as session:
        schedule = Schedule(
            name=data['schedule_name'],
            schedule_type='daily',
            times=valid_times,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(schedule)
        await session.commit()
        
        await register_admin_log(message.from_user.id, "create_schedule", schedule.name)
        
        times_display = ', '.join(valid_times)
        
        await message.answer(
            f"✅ <b>Agendamento criado!</b>\n\n"
            f"📅 Nome: {schedule.name}\n"
            f"🕐 Horários: {times_display}",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


# ==================== FUNÇÕES AUXILIARES ====================

async def check_admin(user_id: int) -> bool:
    """Verifica se usuário é admin"""
    return user_id == settings.ADMIN_ID


async def register_admin_log(admin_id: int, action: str, details: str = None):
    """Registra log administrativo"""
    try:
        async with db_manager.get_session() as session:
            log = AdminLog(
                admin_id=admin_id,
                action=action,
                details=details,
                created_at=datetime.utcnow()
            )
            
            session.add(log)
            await session.commit()
            
    except Exception as e:
        logger.error(f"Erro ao registrar log admin: {e}")
