"""
Sistema completo de suporte e reclamações
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
from typing import Optional, Dict, Any

from database.session import db_manager
from database.models import User, SupportTicket, SupportMessage
from bot.keyboards.user_keyboards import get_main_menu_keyboard
from config import settings

router = Router()

# ID do grupo privado de suporte (configure no .env)
SUPPORT_GROUP_ID = getattr(settings, 'SUPPORT_GROUP_ID', None)


class SupportStates(StatesGroup):
    """Estados do sistema de suporte"""
    waiting_complaint = State()
    waiting_reply = State()
    viewing_ticket = State()


# ==================== MODELOS DE BANCO ====================

class SupportTicket(Base):
    """Modelo de ticket de suporte"""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    
    # Ticket info
    subject = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(50), default="open")  # open, in_progress, resolved, closed
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="support_tickets")
    messages = relationship("SupportMessage", back_populates="ticket")
    
    def __repr__(self):
        return f"<SupportTicket {self.id} - {self.status}>"


class SupportMessage(Base):
    """Modelo de mensagem de suporte"""
    __tablename__ = "support_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    sender_id = Column(BigInteger, nullable=False)  # Telegram ID de quem enviou
    sender_type = Column(String(20), nullable=False)  # user, admin
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    
    def __repr__(self):
        return f"<SupportMessage {self.id} - {self.sender_type}>"


# ==================== HANDLERS DE USUÁRIO ====================

@router.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery, state: FSMContext):
    """Menu de suporte"""
    user_id = callback.from_user.id
    
    keyboard = [
        [InlineKeyboardButton(text="📝 Fazer Reclamação", callback_data="make_complaint")],
        [InlineKeyboardButton(text="📋 Minhas Reclamações", callback_data="my_tickets")],
        [InlineKeyboardButton(text="💬 Falar com Suporte", callback_data="talk_support")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "💬 <b>CENTRAL DE SUPORTE</b>\n\n"
        "Como podemos ajudar?\n\n"
        "• <b>Fazer Reclamação:</b> Registre um problema\n"
        "• <b>Minhas Reclamações:</b> Acompanhe seus tickets\n"
        "• <b>Falar com Suporte:</b> Conversa direta\n\n"
        "Selecione uma opção:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "make_complaint")
async def make_complaint_start(callback: CallbackQuery, state: FSMContext):
    """Inicia formulário de reclamação"""
    user_id = callback.from_user.id
    
    await state.set_state(SupportStates.waiting_complaint)
    
    await callback.message.answer(
        "📝 <b>NOVA RECLAMAÇÃO</b>\n\n"
        "Por favor, explique detalhadamente o que aconteceu:\n\n"
        "• Qual produto/serviço?\n"
        "• O que ocorreu?\n"
        "• Quando aconteceu?\n\n"
        "Envie sua mensagem abaixo:"
    )
    await callback.answer()


@router.message(SupportStates.waiting_complaint)
async def process_complaint(message: Message, state: FSMContext):
    """Processa reclamação e cria ticket"""
    user_id = message.from_user.id
    
    complaint_text = message.text
    
    if len(complaint_text) < 10:
        await message.answer(
            "❌ Reclamação muito curta. Explique melhor o problema:"
        )
        return
    
    # Criar ticket no banco
    async with db_manager.get_session() as session:
        ticket = SupportTicket(
            user_id=user_id,
            user_telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            subject=f"Reclamação de {message.from_user.first_name}",
            description=complaint_text,
            status="open",
            priority="normal",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(ticket)
        await session.commit()
        
        ticket_id = ticket.id
    
    # Enviar confirmação ao usuário
    await message.answer(
        f"✅ <b>RECLAMAÇÃO REGISTRADA!</b>\n\n"
        f"📋 <b>Ticket:</b> #{ticket_id}\n"
        f"📝 <b>Descrição:</b> {complaint_text[:100]}...\n\n"
        "Nossa equipe analisará seu caso e responderá em breve.\n"
        "Você pode acompanhar pelo menu 'Minhas Reclamações'.",
        reply_markup=get_main_menu_keyboard()
    )
    
    # Enviar para o grupo privado
    await send_ticket_to_support_group(message.bot, ticket_id)
    
    await state.clear()
    
    logger.info(f"Ticket #{ticket_id} created by user {user_id}")


async def send_ticket_to_support_group(bot, ticket_id: int):
    """Envia ticket para o grupo privado de suporte"""
    try:
        if not SUPPORT_GROUP_ID:
            logger.warning("SUPPORT_GROUP_ID not configured")
            return
        
        # Buscar ticket completo
        async with db_manager.get_session_no_commit() as session:
            ticket = await session.get(SupportTicket, ticket_id)
            
            if not ticket:
                return
            
            # Formatar mensagem para o grupo
            support_text = (
                f"🔔 <b>NOVA RECLAMAÇÃO</b>\n\n"
                f"📋 <b>Ticket:</b> #{ticket.id}\n"
                f"👤 <b>Usuário:</b> {ticket.first_name or 'N/A'}\n"
                f"🆔 <b>Telegram ID:</b> {ticket.user_telegram_id}\n"
                f"📱 <b>Username:</b> @{ticket.username or 'N/A'}\n"
                f"📅 <b>Data:</b> {ticket.created_at.strftime('%d/%m/%Y')}\n"
                f"🕐 <b>Hora:</b> {ticket.created_at.strftime('%H:%M')}\n"
                f"📝 <b>Reclamação:</b>\n{ticket.description}\n\n"
                f"📊 <b>Status:</b> ABERTO"
            )
            
            # Botões de ação
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="✅ RESOLVIDO",
                        callback_data=f"ticket_resolved_{ticket.id}"
                    ),
                    InlineKeyboardButton(
                        text="💬 RESPONDER",
                        callback_data=f"ticket_reply_{ticket.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔒 FECHAR",
                        callback_data=f"ticket_close_{ticket.id}"
                    ),
                    InlineKeyboardButton(
                        text="⭐ URGENTE",
                        callback_data=f"ticket_urgent_{ticket.id}"
                    )
                ]
            ]
            
            # Enviar para o grupo
            await bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                text=support_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
            logger.info(f"Ticket #{ticket_id} sent to support group")
            
    except Exception as e:
        logger.error(f"Error sending ticket to support group: {e}")


# ==================== HANDLERS ADMIN (NO GRUPO) ====================

@router.callback_query(F.data.startswith("ticket_resolved_"))
async def ticket_resolved(callback: CallbackQuery):
    """Admin marca ticket como resolvido"""
    if not await check_support_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    ticket_id = int(callback.data.replace("ticket_resolved_", ""))
    
    async with db_manager.get_session() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        
        if ticket:
            ticket.status = "resolved"
            ticket.resolved_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()
            await session.commit()
            
            # Notificar usuário
            await callback.bot.send_message(
                chat_id=ticket.user_telegram_id,
                text=(
                    f"✅ <b>TICKET RESOLVIDO!</b>\n\n"
                    f"📋 Ticket: #{ticket.id}\n"
                    f"📝 Sua reclamação foi resolvida!\n\n"
                    "Obrigado pela paciência. Se precisar, estamos à disposição."
                )
            )
            
            # Atualizar mensagem no grupo
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>RESOLVIDO</b>"
            )
            
            await callback.answer("✅ Ticket marcado como resolvido!", show_alert=True)
    
    logger.info(f"Ticket #{ticket_id} resolved")


@router.callback_query(F.data.startswith("ticket_reply_"))
async def ticket_reply_start(callback: CallbackQuery, state: FSMContext):
    """Admin inicia resposta ao ticket"""
    if not await check_support_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    ticket_id = int(callback.data.replace("ticket_reply_", ""))
    
    await state.update_data(replying_ticket_id=ticket_id)
    await state.set_state(SupportStates.waiting_reply)
    
    await callback.message.answer(
        f"💬 <b>RESPONDER TICKET #{ticket_id}</b>\n\n"
        "Envie sua resposta para o cliente:"
    )
    await callback.answer()


@router.message(SupportStates.waiting_reply)
async def process_ticket_reply(message: Message, state: FSMContext):
    """Processa resposta do admin e envia ao cliente"""
    if not await check_support_admin(message.from_user.id):
        await message.answer("⛔ Acesso negado!")
        await state.clear()
        return
    
    data = await state.get_data()
    ticket_id = data.get('replying_ticket_id')
    
    if not ticket_id:
        await message.answer("❌ Erro ao identificar ticket.")
        await state.clear()
        return
    
    reply_text = message.text
    
    # Salvar mensagem
    async with db_manager.get_session() as session:
        support_message = SupportMessage(
            ticket_id=ticket_id,
            sender_id=message.from_user.id,
            sender_type="admin",
            message_text=reply_text,
            created_at=datetime.utcnow()
        )
        session.add(support_message)
        
        # Atualizar ticket
        ticket = await session.get(SupportTicket, ticket_id)
        if ticket:
            ticket.status = "in_progress"
            ticket.updated_at = datetime.utcnow()
        
        await session.commit()
        
        user_telegram_id = ticket.user_telegram_id if ticket else None
    
    # Enviar resposta ao cliente
    if user_telegram_id:
        await message.bot.send_message(
            chat_id=user_telegram_id,
            text=(
                f"💬 <b>RESPOSTA DO SUPORTE</b>\n\n"
                f"📋 Ticket: #{ticket_id}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{reply_text}\n"
                f"━━━━━━━━━━━━━━━━\n\n"
                "Para responder, basta enviar uma mensagem aqui."
            )
        )
        
        await message.answer(
            f"✅ <b>Resposta enviada ao cliente!</b>\n"
            f"Ticket: #{ticket_id}"
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("ticket_close_"))
async def ticket_close(callback: CallbackQuery):
    """Admin fecha ticket"""
    if not await check_support_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    ticket_id = int(callback.data.replace("ticket_close_", ""))
    
    async with db_manager.get_session() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        
        if ticket:
            ticket.status = "closed"
            ticket.closed_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()
            await session.commit()
            
            # Notificar usuário
            await callback.bot.send_message(
                chat_id=ticket.user_telegram_id,
                text=(
                    f"🔒 <b>TICKET FECHADO</b>\n\n"
                    f"📋 Ticket: #{ticket.id}\n"
                    "Este ticket foi fechado.\n"
                    "Se precisar de ajuda novamente, abra uma nova reclamação."
                )
            )
            
            # Atualizar mensagem no grupo
            await callback.message.edit_text(
                callback.message.text + "\n\n🔒 <b>FECHADO</b>"
            )
            
            await callback.answer("🔒 Ticket fechado!", show_alert=True)
    
    logger.info(f"Ticket #{ticket_id} closed")


@router.callback_query(F.data.startswith("ticket_urgent_"))
async def ticket_urgent(callback: CallbackQuery):
    """Admin marca ticket como urgente"""
    if not await check_support_admin(callback.from_user.id):
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    ticket_id = int(callback.data.replace("ticket_urgent_", ""))
    
    async with db_manager.get_session() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        
        if ticket:
            ticket.priority = "urgent"
            ticket.updated_at = datetime.utcnow()
            await session.commit()
            
            await callback.message.edit_text(
                callback.message.text + "\n\n⭐ <b>URGENTE</b>"
            )
            
            await callback.answer("⭐ Ticket marcado como urgente!", show_alert=True)


# ==================== CONVERSA BIDIRECIONAL ====================

@router.message(F.text)
async def handle_support_conversation(message: Message):
    """
    Gerencia conversa bidirecional entre admin e cliente
    """
    user_id = message.from_user.id
    
    # Verificar se é admin respondendo
    if user_id == settings.ADMIN_ID:
        # Admin está no grupo de suporte
        if message.chat.id == SUPPORT_GROUP_ID:
            # Verificar se está respondendo a um ticket
            async with db_manager.get_session_no_commit() as session:
                from sqlalchemy import select
                
                # Buscar ticket mais recente em andamento
                result = await session.execute(
                    select(SupportTicket)
                    .where(SupportTicket.status.in_(["open", "in_progress"]))
                    .order_by(SupportTicket.updated_at.desc())
                    .limit(1)
                )
                ticket = result.scalar_one_or_none()
                
                if ticket:
                    # Enviar mensagem ao cliente
                    await message.bot.send_message(
                        chat_id=ticket.user_telegram_id,
                        text=(
                            f"💬 <b>SUPORTE:</b>\n"
                            f"{message.text}"
                        )
                    )
                    
                    # Salvar mensagem
                    async with db_manager.get_session() as save_session:
                        support_message = SupportMessage(
                            ticket_id=ticket.id,
                            sender_id=user_id,
                            sender_type="admin",
                            message_text=message.text,
                            created_at=datetime.utcnow()
                        )
                        save_session.add(support_message)
                        await save_session.commit()
    
    else:
        # Cliente respondendo
        async with db_manager.get_session_no_commit() as session:
            from sqlalchemy import select
            
            # Buscar ticket aberto do usuário
            result = await session.execute(
                select(SupportTicket)
                .where(SupportTicket.user_telegram_id == user_id)
                .where(SupportTicket.status.in_(["open", "in_progress"]))
                .order_by(SupportTicket.updated_at.desc())
                .limit(1)
            )
            ticket = result.scalar_one_or_none()
            
            if ticket:
                # Encaminhar mensagem ao grupo de suporte
                if SUPPORT_GROUP_ID:
                    await message.bot.send_message(
                        chat_id=SUPPORT_GROUP_ID,
                        text=(
                            f"💬 <b>RESPOSTA DO CLIENTE</b>\n\n"
                            f"📋 Ticket: #{ticket.id}\n"
                            f"👤 {message.from_user.first_name}:\n"
                            f"{message.text}"
                        )
                    )
                    
                    # Salvar mensagem
                    async with db_manager.get_session() as save_session:
                        support_message = SupportMessage(
                            ticket_id=ticket.id,
                            sender_id=user_id,
                            sender_type="user",
                            message_text=message.text,
                            created_at=datetime.utcnow()
                        )
                        save_session.add(support_message)
                        await save_session.commit()
                    
                    await message.answer(
                        "✅ Mensagem enviada ao suporte!"
                    )


@router.callback_query(F.data == "my_tickets")
async def my_tickets(callback: CallbackQuery):
    """Mostra tickets do usuário"""
    user_id = callback.from_user.id
    
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(SupportTicket)
            .where(SupportTicket.user_telegram_id == user_id)
            .order_by(SupportTicket.created_at.desc())
            .limit(10)
        )
        tickets = result.scalars().all()
    
    if not tickets:
        await callback.message.answer(
            "📋 <b>MINHAS RECLAMAÇÕES</b>\n\n"
            "Você não tem reclamações registradas.",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return
    
    tickets_text = "📋 <b>MINHAS RECLAMAÇÕES</b>\n\n"
    
    for ticket in tickets:
        status_emoji = {
            "open": "🔓",
            "in_progress": "🔄",
            "resolved": "✅",
            "closed": "🔒"
        }.get(ticket.status, "📋")
        
        tickets_text += (
            f"{status_emoji} <b>Ticket #{ticket.id}</b>\n"
            f"📅 {ticket.created_at.strftime('%d/%m/%Y %H:%M')}\n"
            f"📝 {ticket.description[:50]}...\n"
            f"📊 Status: {ticket.status}\n\n"
        )
    
    await callback.message.answer(
        tickets_text,
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


async def check_support_admin(user_id: int) -> bool:
    """Verifica se usuário é admin de suporte"""
    return user_id == settings.ADMIN_ID
