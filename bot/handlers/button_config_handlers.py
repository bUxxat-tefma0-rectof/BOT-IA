"""
Handlers para configuração de botões
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional, List

from database.session import db_manager
from database.models import ButtonConfig
from bot.keyboards.admin_keyboards import get_admin_main_menu
from services.button_config_service import ButtonConfigService
from config import settings

router = Router()
button_service = ButtonConfigService()


class ButtonStates(StatesGroup):
    """Estados para configuração de botões"""
    waiting_name = State()
    waiting_text = State()
    waiting_emoji = State()
    waiting_action = State()
    waiting_callback = State()
    waiting_url = State()
    waiting_position = State()
    editing_button = State()


@router.callback_query(F.data == "admin_list_buttons")
async def list_buttons(callback: CallbackQuery):
    """Lista botões configurados"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    buttons = await button_service.get_active_buttons()
    
    if not buttons:
        await callback.message.answer(
            "🔘 <b>Nenhum botão configurado</b>\n\n"
            "Crie botões personalizados para suas publicações.",
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        return
    
    # Criar teclado com botões
    keyboard = []
    for button in buttons:
        keyboard.append([InlineKeyboardButton(
            text=f"{button.emoji or '🔘'} {button.text} (Linha {button.row}, Pos {button.position})",
            callback_data=f"view_button_{button.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="➕ Novo Botão",
        callback_data="admin_new_button"
    )])
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_main"
    )])
    
    await callback.message.edit_text(
        "🔘 <b>BOTÕES CONFIGURADOS</b>\n\n"
        f"Total: {len(buttons)} botões ativos\n"
        "Clique em um botão para gerenciar:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_new_button")
async def new_button(callback: CallbackQuery, state: FSMContext):
    """Inicia criação de novo botão"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    await state.set_state(ButtonStates.waiting_name)
    await callback.message.answer(
        "🔘 <b>NOVO BOTÃO</b>\n\n"
        "Envie um nome identificador para o botão:"
    )
    await callback.answer()


@router.message(ButtonStates.waiting_name)
async def process_button_name(message: Message, state: FSMContext):
    """Processa nome do botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    name = message.text.strip()
    
    await state.update_data(button_name=name)
    await state.set_state(ButtonStates.waiting_text)
    
    await message.answer(
        f"✅ Nome: <b>{name}</b>\n\n"
        "Agora envie o texto que aparecerá no botão:"
    )


@router.message(ButtonStates.waiting_text)
async def process_button_text(message: Message, state: FSMContext):
    """Processa texto do botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    text = message.text.strip()
    
    await state.update_data(button_text=text)
    await state.set_state(ButtonStates.waiting_emoji)
    
    await message.answer(
        f"✅ Texto: <b>{text}</b>\n\n"
        "Envie um emoji para o botão (ou /pular):"
    )


@router.message(ButtonStates.waiting_emoji)
async def process_button_emoji(message: Message, state: FSMContext):
    """Processa emoji do botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    emoji = message.text.strip()
    if emoji == '/pular':
        emoji = None
    
    await state.update_data(button_emoji=emoji)
    
    # Menu de ação
    keyboard = [
        [InlineKeyboardButton(text="🔗 URL", callback_data="button_action_url")],
        [InlineKeyboardButton(text="🔘 Callback", callback_data="button_action_callback")],
        [InlineKeyboardButton(text="🤖 Deep Link", callback_data="button_action_deeplink")],
    ]
    
    await message.answer(
        f"✅ Emoji: {emoji or 'Nenhum'}\n\n"
        "Selecione o tipo de ação:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    
    await state.set_state(ButtonStates.waiting_action)


@router.callback_query(F.data.startswith("button_action_"))
async def process_button_action(callback: CallbackQuery, state: FSMContext):
    """Processa tipo de ação do botão"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    action_type = callback.data.replace("button_action_", "")
    
    await state.update_data(button_action=action_type)
    
    if action_type == 'url':
        await callback.message.answer(
            "Envie a URL do botão:"
        )
        await state.set_state(ButtonStates.waiting_url)
    else:
        await callback.message.answer(
            "Envie o callback data (ex: buy_product_{product_id}):"
        )
        await state.set_state(ButtonStates.waiting_callback)
    
    await callback.answer()


@router.message(ButtonStates.waiting_url)
async def process_button_url(message: Message, state: FSMContext):
    """Processa URL do botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    url = message.text.strip()
    
    if not url.startswith('http'):
        await message.answer("❌ URL inválida. Envie novamente:")
        return
    
    await state.update_data(button_url=url)
    await state.set_state(ButtonStates.waiting_position)
    
    await message.answer(
        "✅ URL salva!\n\n"
        "Agora envie a posição do botão (linha,posição):\n"
        "Exemplo: 0,0 (primeira linha, primeira posição)"
    )


@router.message(ButtonStates.waiting_callback)
async def process_button_callback(message: Message, state: FSMContext):
    """Processa callback do botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    callback_data = message.text.strip()
    
    await state.update_data(button_callback=callback_data)
    await state.set_state(ButtonStates.waiting_position)
    
    await message.answer(
        "✅ Callback salvo!\n\n"
        "Agora envie a posição do botão (linha,posição):\n"
        "Exemplo: 0,0 (primeira linha, primeira posição)"
    )


@router.message(ButtonStates.waiting_position)
async def process_button_position(message: Message, state: FSMContext):
    """Processa posição e cria botão"""
    if message.from_user.id != settings.ADMIN_ID:
        return
    
    try:
        position_text = message.text.strip()
        parts = position_text.split(',')
        
        row = int(parts[0].strip())
        position = int(parts[1].strip()) if len(parts) > 1 else 0
        
        data = await state.get_data()
        
        button_data = {
            'name': data.get('button_name'),
            'text': data.get('button_text'),
            'emoji': data.get('button_emoji'),
            'action_type': data.get('button_action', 'callback'),
            'url': data.get('button_url'),
            'callback_data': data.get('button_callback'),
            'position': position,
            'row': row
        }
        
        button = await button_service.create_button(button_data)
        
        if button:
            await message.answer(
                f"✅ <b>BOTÃO CRIADO!</b>\n\n"
                f"{button.emoji or ''} <b>Texto:</b> {button.text}\n"
                f"📐 <b>Posição:</b> Linha {button.row}, Posição {button.position}\n\n"
                "O botão está pronto para uso!",
                reply_markup=get_admin_main_menu()
            )
        else:
            await message.answer(
                "❌ Erro ao criar botão.",
                reply_markup=get_admin_main_menu()
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Formato inválido. Use linha,posição (ex: 0,0):"
        )


@router.callback_query(F.data.startswith("view_button_"))
async def view_button(callback: CallbackQuery):
    """Visualiza botão específico"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    button_id = int(callback.data.replace("view_button_", ""))
    
    async with db_manager.get_session_no_commit() as session:
        button = await session.get(ButtonConfig, button_id)
    
    if not button:
        await callback.answer("❌ Botão não encontrado", show_alert=True)
        return
    
    button_text = (
        f"🔘 <b>BOTÃO</b>\n\n"
        f"📝 <b>Nome:</b> {button.name}\n"
        f"{button.emoji or ''} <b>Texto:</b> {button.text}\n"
        f"🔗 <b>Ação:</b> {button.action_type}\n"
    )
    
    if button.url:
        button_text += f"🌐 <b>URL:</b> {button.url}\n"
    
    if button.callback_data:
        button_text += f"🔘 <b>Callback:</b> {button.callback_data}\n"
    
    button_text += (
        f"📐 <b>Posição:</b> Linha {button.row}, Posição {button.position}\n"
        f"✅ <b>Ativo:</b> {'Sim' if button.is_active else 'Não'}"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"delete_button_{button.id}")],
        [InlineKeyboardButton(
            text="🔄 Desativar" if button.is_active else "✅ Ativar",
            callback_data=f"toggle_button_{button.id}"
        )],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_list_buttons")]
    ]
    
    await callback.message.edit_text(
        button_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_button_"))
async def delete_button(callback: CallbackQuery):
    """Exclui botão"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    button_id = int(callback.data.replace("delete_button_", ""))
    
    async with db_manager.get_session() as session:
        button = await session.get(ButtonConfig, button_id)
        
        if button:
            await session.delete(button)
            await session.commit()
            
            await callback.message.answer(
                "✅ <b>Botão excluído!</b>",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_button_"))
async def toggle_button(callback: CallbackQuery):
    """Ativa/desativa botão"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    button_id = int(callback.data.replace("toggle_button_", ""))
    
    async with db_manager.get_session() as session:
        button = await session.get(ButtonConfig, button_id)
        
        if button:
            button.is_active = not button.is_active
            button.updated_at = datetime.utcnow()
            await session.commit()
            
            status = "ativado" if button.is_active else "desativado"
            await callback.message.answer(
                f"✅ Botão <b>{status}</b>!",
                reply_markup=get_admin_main_menu()
            )
    
    await callback.answer()
