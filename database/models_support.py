"""
Modelos do sistema de suporte
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, BigInteger, JSON, Enum
from sqlalchemy.orm import relationship
from database.models import Base, User
import enum


class TicketStatus(enum.Enum):
    """Status do ticket"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(enum.Enum):
    """Prioridade do ticket"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


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
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN)
    priority = Column(Enum(TicketPriority), default=TicketPriority.NORMAL)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Relacionamentos
    user = relationship("User", back_populates="support_tickets")
    messages = relationship("SupportMessage", back_populates="ticket", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SupportTicket {self.id} - {self.status}>"


class SupportMessage(Base):
    """Modelo de mensagem de suporte"""
    __tablename__ = "support_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    sender_id = Column(BigInteger, nullable=False)
    sender_type = Column(String(20), nullable=False)  # user, admin
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    ticket = relationship("SupportTicket", back_populates="messages")
    
    def __repr__(self):
        return f"<SupportMessage {self.id} - {self.sender_type}>"


# Adicionar relacionamento na classe User
User.support_tickets = relationship("SupportTicket", back_populates="user")
