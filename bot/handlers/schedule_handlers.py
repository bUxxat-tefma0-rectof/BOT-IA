"""
Handlers para gerenciamento de agendamentos
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from database.session import db_manager
from database.models import Schedule, Product, Category, Publication
from bot.keyboards.admin_keyboards import get_admin_main_menu, get_schedule_menu
from services.schedule_service import ScheduleService
from config import settings

router = Router()
schedule_service = ScheduleService()


class ScheduleStates(StatesGroup):
    """Estados para criação de agendamento"""
    waiting_name = State()
    waiting_type = State()
    waiting_time = State()
    waiting_days = State()
    waiting_product = State()
    waiting_category = State()
    editing_schedule = State()


@router.callback_query(F.data == "admin_view_schedule")
async def view_schedules(callback: CallbackQuery):
    """Visualiza todos os agendamentos"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    schedules = await schedule_service.get_all_schedules()
    
    if not schedules:
        await callback.message.answer(
            "📅 <b>Nenhum agendamento criado</b>\n\n"
            "Crie agendamentos para publicar automaticamente.",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com agendamentos
    keyboard = []
    for schedule in schedules:
        status_emoji = "✅" if schedule.is_active else "❌"
        times = ", ".join(schedule.times or []) if schedule.times else "N/A"
        
        keyboard.append([InlineKeyboardButton(
            text=f"{status_emoji} {schedule.name} ({times})",
            callback_data=f"view_schedule_{schedule.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_schedules"
    )])
    
    await callback.message.edit_text(
        "📅 <b>AGENDAMENTOS</b>\n\n"
        f"Total: {len(schedules)} agendamentos\n"
        "Clique em um agendamento para gerenciar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_new_schedule")
async def new_schedule(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de novo agendamento"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await state.set_state(ScheduleStates.waiting_name)
    await callback.message.answer(
        "📅 <b>NOVO AGENDAMENTO</b>\n\n"
        "Envie um nome para o agendamento:"
    )
    await callback.answer()


@router.message(ScheduleStates.waiting_name)
async def process_schedule_name(message: Message, state: FSMContext):
    """Processa nome do agendamento"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    name = message.text.strip()
    
    if len(name) < 3:
        await message.answer("❌ Nome muito curto. Envie novamente:")
        return
    
    await state.update_data(schedule_name=name)
    
    # Menu de tipo
    keyboard = [
        [InlineKeyboardButton(text="📅 Diário", callback_data="schedule_type_daily")],
        [InlineKeyboardButton(text="📅 Semanal", callback_data="schedule_type_weekly")],
        [InlineKeyboardButton(text="📅 Personalizado", callback_data="schedule_type_custom")],
    ]
    
    await message.answer(
        f"✅ Nome: <b>{name}</b>\n\n"
        "Selecione o tipo de agendamento:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    
    await state.set_state(ScheduleStates.waiting_type)


@router.callback_query(F.data.startswith("schedule_type_"))
async def process_schedule_type(callback: CallbackQuery, state: FSMContext):
    """Processa tipo de agendamento"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    schedule_type = callback.data.replace("schedule_type_", "")
    
    await state.update_data(schedule_type=schedule_type)
    
    await callback.message.answer(
        f"✅ Tipo: <b>{schedule_type}</b>\n\n"
        "Agora envie os horários (formato HH:MM, separados por vírgula):\n"
        "Exemplo: 09:00, 12:00, 15:00, 18:00"
    )
    
    await state.set_state(ScheduleStates.waiting_time)
    await callback.answer()


@router.message(ScheduleStates.waiting_time)
async def process_schedule_time(message: Message, state: FSMContext):
    """Processa horários do agendamento"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    times_text = message.text.strip()
    times = [t.strip() for t in times_text.split(',')]
    
    # Validar horários
    import re
    time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    
    valid_times = []
    for time_str in times:
        if re.match(time_pattern, time_str):
            valid_times.append(time_str)
        else:
            await message.answer(
                f"❌ Horário inválido: {time_str}\n"
                "Use formato HH:MM. Envie novamente:"
            )
            return
    
    await state.update_data(schedule_times=valid_times)
    
    # Se for semanal, perguntar dias
    data = await state.get_data()
    if data.get('schedule_type') == 'weekly':
        await message.answer(
            "✅ Horários salvos!\n\n"
            "Agora selecione os dias da semana (0=Segunda, 6=Domingo):\n"
            "Exemplo: 0,1,2,3,4 (segunda a sexta)"
        )
        await state.set_state(ScheduleStates.waiting_days)
    else:
        # Para diário ou personalizado, ir direto para produto
        await message.answer(
            "✅ Horários salvos!\n\n"
            "Agora selecione o produto (ou envie /pular para categoria):"
        )
        await state.set_state(ScheduleStates.waiting_product)


@router.message(ScheduleStates.waiting_days)
async def process_schedule_days(message: Message, state: FSMContext):
    """Processa dias da semana"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    days_text = message.text.strip()
    
    try:
        days = [int(d.strip()) for d in days_text.split(',')]
        
        # Validar dias
        for day in days:
            if day < 0 or day > 6:
                await message.answer(
                    "❌ Dia inválido. Use 0 (segunda) a 6 (domingo). Envie novamente:"
                )
                return
        
        await state.update_data(schedule_days=days)
        
        await message.answer(
            "✅ Dias salvos!\n\n"
            "Agora selecione o produto (ou envie /pular para usar categoria):"
        )
        await state.set_state(ScheduleStates.waiting_product)
        
    except ValueError:
        await message.answer("❌ Formato inválido. Envie números separados por vírgula:")


@router.message(ScheduleStates.waiting_product)
async def process_schedule_product(message: Message, state: FSMContext):
    """Processa produto do agendamento"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    if message.text == '/pular':
        await state.update_data(schedule_product_id=None)
        await message.answer(
            "Agora selecione a categoria (ou envie /pular para usar ofertas ativas):"
        )
        await state.set_state(ScheduleStates.waiting_category)
        return
    
    # Buscar produto pelo nome ou código
    from services.product_service import ProductService
    product_service = ProductService()
    
    query = message.text.strip()
    products = await product_service.search_products(query)
    
    if not products:
        await message.answer(
            "❌ Produto não encontrado. Envie outro termo ou /pular:"
        )
        return
    
    if len(products) == 1:
        product = products[0]
        await state.update_data(schedule_product_id=product.id)
        
        await message.answer(
            f"✅ Produto: <b>{product.name}</b>\n\n"
            "Envie a categoria (ou /pular para finalizar):"
        )
        await state.set_state(ScheduleStates.waiting_category)
    else:
        # Mostrar opções
        keyboard = []
        for product in products[:10]:
            keyboard.append([InlineKeyboardButton(
                text=f"📦 {product.name}",
                callback_data=f"select_schedule_product_{product.id}"
            )])
        
        await message.answer(
            "Selecione o produto:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )


@router.callback_query(F.data.startswith("select_schedule_product_"))
async def select_schedule_product(callback: CallbackQuery, state: FSMContext):
    """Seleciona produto para agendamento"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    product_id = int(callback.data.replace("select_schedule_product_", ""))
    
    await state.update_data(schedule_product_id=product_id)
    
    await callback.message.answer(
        "✅ Produto selecionado!\n\n"
        "Envie a categoria (ou /pular para finalizar):"
    )
    await state.set_state(ScheduleStates.waiting_category)
    await callback.answer()


@router.message(ScheduleStates.waiting_category)
async def process_schedule_category(message: Message, state: FSMContext):
    """Processa categoria e finaliza agendamento"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    category_id = None
    
    if message.text != '/pular':
        # Buscar categoria
        from services.product_service import ProductService
        product_service = ProductService()
        
        categories = await product_service.get_categories()
        
        for category in categories:
            if category.name.lower() == message.text.lower():
                category_id = category.id
                break
        
        if not category_id:
            await message.answer(
                "❌ Categoria não encontrada. Envie outro nome ou /pular:"
            )
            return
    
    # Criar agendamento
    data = await state.get_data()
    
    schedule_data = {
        'name': data.get('schedule_name'),
        'schedule_type': data.get('schedule_type', 'daily'),
        'times': data.get('schedule_times', []),
        'days_of_week': data.get('schedule_days'),
        'product_id': data.get('schedule_product_id'),
        'category_id': category_id
    }
    
    schedule = await schedule_service.create_schedule(schedule_data)
    
    if schedule:
        await message.answer(
            f"✅ <b>AGENDAMENTO CRIADO!</b>\n\n"
            f"📅 Nome: {schedule.name}\n"
            f"🕐 Horários: {', '.join(schedule.times)}\n"
            f"📦 Produto ID: {schedule.product_id or 'N/A'}\n"
            f"📂 Categoria ID: {schedule.category_id or 'N/A'}\n\n"
            "O agendamento está ativo!",
            reply_markup=get_admin_main_menu()
        )
    else:
        await message.answer(
            "❌ Erro ao criar agendamento.",
            reply_markup=get_admin_main_menu()
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("view_schedule_"))
async def view_schedule(callback: CallbackQuery):
    """Visualiza agendamento específico"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    schedule_id = int(callback.data.replace("view_schedule_", ""))
    schedule = await schedule_service.get_schedule(schedule_id)
    
    if not schedule:
        await callback.answer("❌ Agendamento não encontrado", show_alert=True)
        return
    
    schedule_text = (
        f"📅 <b>AGENDAMENTO</b>\n\n"
        f"📝 <b>Nome:</b> {schedule.name}\n"
        f"🕐 <b>Horários:</b> {', '.join(schedule.times or [])}\n"
        f"📅 <b>Tipo:</b> {schedule.schedule_type}\n"
    )
    
    if schedule.days_of_week:
        days_names = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        days_text = ", ".join([days_names[d] for d in schedule.days_of_week])
        schedule_text += f"📆 <b>Dias:</b> {days_text}\n"
    
    schedule_text += f"✅ <b>Ativo:</b> {'Sim' if schedule.is_active else 'Não'}\n"
    
    keyboard = [
        [InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"delete_schedule_{schedule.id}")],
        [InlineKeyboardButton(
            text="🔄 Desativar" if schedule.is_active else "✅ Ativar",
            callback_data=f"toggle_schedule_{schedule.id}"
        )],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_view_schedule")]
    ]
    
    await callback.message.edit_text(
        schedule_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_schedule_"))
async def delete_schedule(callback: CallbackQuery):
    """Exclui agendamento"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    schedule_id = int(callback.data.replace("delete_schedule_", ""))
    
    success = await schedule_service.delete_schedule(schedule_id)
    
    if success:
        await callback.message.answer(
            "✅ <b>Agendamento excluído!</b>",
            reply_markup=get_admin_main_menu()
        )
    else:
        await callback.message.answer(
            "❌ Erro ao excluir agendamento.",
            reply_markup=get_admin_main_menu()
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_schedule_"))
async def toggle_schedule(callback: CallbackQuery):
    """Ativa/desativa agendamento"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    schedule_id = int(callback.data.replace("toggle_schedule_", ""))
    
    async with db_manager.get_session() as session:
        schedule = await session.get(Schedule, schedule_id)
        
        if schedule:
            schedule.is_active = not schedule.is_active
            schedule.updated_at = datetime.utcnow()
            await session.commit()
            
            status = "ativado" if schedule.is_active else "desativado"
            await callback.message.answer(
                f"✅ Agendamento <b>{status}</b>!",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()
