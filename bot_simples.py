import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "6600992558:AAGJKHdbIDy8j5VVm2D3PH2A6SxEKWZZja0")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6995978182"))
SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID", "-1002170539293")

class SupportStates(StatesGroup):
    waiting_complaint = State()
    waiting_reply = State()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

def get_user_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="💬 Fazer Reclamação", callback_data="make_complaint")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Olá {message.from_user.first_name}!\n\nComo posso ajudar?",
        reply_markup=get_user_keyboard()
    )

@dp.callback_query(F.data == "make_complaint")
async def make_complaint(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_complaint)
    
    # FORCE REPLY - Abre a caixa de digitação automaticamente
    await callback.message.answer(
        "📝 <b>Explique o que aconteceu:</b>\n\n"
        "Digite sua reclamação abaixo 👇",
        reply_markup=ForceReply(selective=True)
    )
    await callback.answer()

@dp.message(SupportStates.waiting_complaint)
async def process_complaint(message: Message, state: FSMContext):
    support_text = (
        f"🔔 <b>NOVA RECLAMAÇÃO</b>\n\n"
        f"👤 <b>Nome:</b> {message.from_user.first_name}\n"
        f"🆔 <b>ID:</b> {message.from_user.id}\n"
        f"📱 <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
        f"📅 <b>Data:</b> {datetime.now().strftime('%d/%m/%Y')}\n"
        f"🕐 <b>Hora:</b> {datetime.now().strftime('%H:%M')}\n\n"
        f"📝 <b>Reclamação:</b>\n{message.text}"
    )
    keyboard = [
        [
            InlineKeyboardButton(text="✅ RESOLVIDO", callback_data=f"resolved_{message.from_user.id}"),
            InlineKeyboardButton(text="💬 RESPONDER", callback_data=f"reply_{message.from_user.id}"),
        ],
        [
            InlineKeyboardButton(text="🔒 FECHAR", callback_data=f"close_{message.from_user.id}"),
        ]
    ]
    
    try:
        await message.bot.send_message(
            chat_id=SUPPORT_GROUP_ID,
            text=support_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await message.answer("✅ Reclamação enviada!")
    except Exception as e:
        await message.answer("❌ Erro ao enviar. Tente novamente.")
    
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def reply_to_user(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    user_id = int(callback.data.replace("reply_", ""))
    await state.update_data(replying_to=user_id)
    await state.set_state(SupportStates.waiting_reply)
    
    # FORCE REPLY para admin responder
    await callback.message.answer(
        "💬 <b>Envie sua resposta:</b>",
        reply_markup=ForceReply(selective=True)
    )
    await callback.answer()

@dp.message(SupportStates.waiting_reply)
async def send_reply(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    user_id = data.get('replying_to')
    if user_id:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"💬 <b>RESPOSTA DO SUPORTE:</b>\n\n{message.text}"
        )
        await message.answer("✅ Resposta enviada!")
    await state.clear()

@dp.callback_query(F.data.startswith("resolved_"))
async def mark_resolved(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    user_id = int(callback.data.replace("resolved_", ""))
    try:
        await callback.bot.send_message(chat_id=user_id, text="✅ Sua reclamação foi RESOLVIDA!")
    except:
        pass
    await callback.message.edit_text(callback.message.text + "\n\n✅ RESOLVIDO")
    await callback.answer("✅ Resolvido!")

@dp.callback_query(F.data.startswith("close_"))
async def close_ticket(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    user_id = int(callback.data.replace("close_", ""))
    try:
        await callback.bot.send_message(chat_id=user_id, text="🔒 Ticket fechado.")
    except:
        pass
    await callback.message.edit_text(callback.message.text + "\n\n🔒 FECHADO")
    await callback.answer("🔒 Fechado!")

async def main():
    print("🤖 Bot iniciado!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
