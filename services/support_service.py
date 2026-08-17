"""
Serviço de suporte e tickets
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
from loguru import logger

from database.session import db_manager
from database.models_support import SupportTicket, SupportMessage, TicketStatus, TicketPriority
from redis_manager import redis_manager


class SupportService:
    """Serviço para gerenciamento de suporte"""
    
    def __init__(self):
        self.cache_prefix = "support:"
        self.cache_ttl = 300
    
    async def create_ticket(self, user_data: Dict[str, Any]) -> Optional[SupportTicket]:
        """Cria novo ticket"""
        try:
            async with db_manager.get_session() as session:
                ticket = SupportTicket(
                    user_id=user_data.get('user_id'),
                    user_telegram_id=user_data.get('user_telegram_id'),
                    username=user_data.get('username'),
                    first_name=user_data.get('first_name'),
                    subject=user_data.get('subject', 'Reclamação'),
                    description=user_data.get('description'),
                    status=TicketStatus.OPEN,
                    priority=TicketPriority.NORMAL,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(ticket)
                await session.commit()
                
                logger.info(f"Ticket created: #{ticket.id}")
                return ticket
                
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return None
    
    async def get_ticket(self, ticket_id: int) -> Optional[SupportTicket]:
        """Busca ticket por ID"""
        try:
            async with db_manager.get_session_no_commit() as session:
                ticket = await session.get(SupportTicket, ticket_id)
                return ticket
                
        except Exception as e:
            logger.error(f"Error getting ticket: {e}")
            return None
    
    async def get_user_tickets(self, user_telegram_id: int) -> List[SupportTicket]:
        """Busca tickets de um usuário"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(SupportTicket)
                    .where(SupportTicket.user_telegram_id == user_telegram_id)
                    .order_by(SupportTicket.created_at.desc())
                )
                tickets = result.scalars().all()
                
                return list(tickets)
                
        except Exception as e:
            logger.error(f"Error getting user tickets: {e}")
            return []
    
    async def get_open_tickets(self) -> List[SupportTicket]:
        """Busca tickets abertos"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(SupportTicket)
                    .where(SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
                    .order_by(SupportTicket.created_at.desc())
                )
                tickets = result.scalars().all()
                
                return list(tickets)
                
        except Exception as e:
            logger.error(f"Error getting open tickets: {e}")
            return []
    
    async def update_ticket_status(self, ticket_id: int, status: TicketStatus) -> bool:
        """Atualiza status do ticket"""
        try:
            async with db_manager.get_session() as session:
                ticket = await session.get(SupportTicket, ticket_id)
                
                if not ticket:
                    return False
                
                ticket.status = status
                ticket.updated_at = datetime.utcnow()
                
                if status == TicketStatus.RESOLVED:
                    ticket.resolved_at = datetime.utcnow()
                elif status == TicketStatus.CLOSED:
                    ticket.closed_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(f"Ticket #{ticket_id} status updated to {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")
            return False
    
    async def add_message(self, ticket_id: int, sender_id: int, sender_type: str, message_text: str) -> Optional[SupportMessage]:
        """Adiciona mensagem ao ticket"""
        try:
            async with db_manager.get_session() as session:
                message = SupportMessage(
                    ticket_id=ticket_id,
                    sender_id=sender_id,
                    sender_type=sender_type,
                    message_text=message_text,
                    created_at=datetime.utcnow()
                )
                
                session.add(message)
                
                # Atualizar ticket
                ticket = await session.get(SupportTicket, ticket_id)
                if ticket:
                    ticket.updated_at = datetime.utcnow()
                    if ticket.status == TicketStatus.OPEN:
                        ticket.status = TicketStatus.IN_PROGRESS
                
                await session.commit()
                
                logger.info(f"Message added to ticket #{ticket_id}")
                return message
                
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return None
    
    async def get_ticket_messages(self, ticket_id: int) -> List[SupportMessage]:
        """Busca mensagens de um ticket"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(SupportMessage)
                    .where(SupportMessage.ticket_id == ticket_id)
                    .order_by(SupportMessage.created_at)
                )
                messages = result.scalars().all()
                
                return list(messages)
                
        except Exception as e:
            logger.error(f"Error getting ticket messages: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Busca estatísticas de suporte"""
        try:
            async with db_manager.get_session_no_commit() as session:
                total = await session.scalar(
                    select(func.count(SupportTicket.id))
                )
                
                open_count = await session.scalar(
                    select(func.count(SupportTicket.id))
                    .where(SupportTicket.status == TicketStatus.OPEN)
                )
                
                in_progress = await session.scalar(
                    select(func.count(SupportTicket.id))
                    .where(SupportTicket.status == TicketStatus.IN_PROGRESS)
                )
                
                resolved = await session.scalar(
                    select(func.count(SupportTicket.id))
                    .where(SupportTicket.status == TicketStatus.RESOLVED)
                )
                
                closed = await session.scalar(
                    select(func.count(SupportTicket.id))
                    .where(SupportTicket.status == TicketStatus.CLOSED)
                )
                
                return {
                    'total_tickets': total or 0,
                    'open_tickets': open_count or 0,
                    'in_progress': in_progress or 0,
                    'resolved': resolved or 0,
                    'closed': closed or 0
                }
                
        except Exception as e:
            logger.error(f"Error getting support statistics: {e}")
            return {}
