"""
Modelos do banco de dados
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, Float, BigInteger, JSON, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class UserStatus(enum.Enum):
    """Status do usuário no sistema"""
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    ADMIN = "admin"


class OfferStatus(enum.Enum):
    """Status da oferta"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AlertStatus(enum.Enum):
    """Status do alerta"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"


class User(Base):
    """Modelo de usuário"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_channel_member = Column(Boolean, default=False)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_interaction = Column(DateTime, nullable=True)
    
    # Relacionamentos
    alerts = relationship("Alert", back_populates="user")
    interactions = relationship("UserInteraction", back_populates="user")
    source_tracking = relationship("SourceTracking", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.telegram_id} - {self.username}>"


class Category(Base):
    """Modelo de categoria"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    emoji = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    products = relationship("Product", back_populates="category")
    
    def __repr__(self):
        return f"<Category {self.name}>"


class Product(Base):
    """Modelo de produto/oferta"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(String(50), unique=True, nullable=False, index=True)  # ID único tipo #892
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(1000), nullable=True)
    
    # Preços
    original_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    discount_percentage = Column(Float, nullable=True)
    
    # Links
    shopee_link = Column(String(1000), nullable=True)
    affiliate_link = Column(String(1000), nullable=True)
    
    # Relacionamento com categoria
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="products")
    
    # Status e monitoramento
    status = Column(Enum(OfferStatus), default=OfferStatus.DRAFT)
    is_monitoring = Column(Boolean, default=False)
    monitoring_config = Column(JSON, nullable=True)
    
    # Datas
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Template
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    template = relationship("Template", back_populates="products")
    
    # Relacionamentos
    alerts = relationship("Alert", back_populates="product")
    publications = relationship("Publication", back_populates="product")
    interactions = relationship("UserInteraction", back_populates="product")
    
    def __repr__(self):
        return f"<Product {self.product_code} - {self.name}>"


class Alert(Base):
    """Modelo de alerta de usuário"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE)
    
    # Condições do alerta
    alert_conditions = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True)
    
    # Relacionamentos
    user = relationship("User", back_populates="alerts")
    product = relationship("Product", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert User:{self.user_id} Product:{self.product_id} - {self.status}>"


class Template(Base):
    """Modelo de template de publicação"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template structure
    template_text = Column(Text, nullable=True)
    template_buttons = Column(JSON, nullable=True)
    template_image = Column(String(1000), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    products = relationship("Product", back_populates="template")
    publications = relationship("Publication", back_populates="template")
    
    def __repr__(self):
        return f"<Template {self.name}>"


class Publication(Base):
    """Modelo de publicação no canal"""
    __tablename__ = "publications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    
    # Mensagem no Telegram
    channel_message_id = Column(BigInteger, nullable=True)
    message_text = Column(Text, nullable=True)
    
    status = Column(Enum(OfferStatus), default=OfferStatus.DRAFT)
    
    # Agendamento
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Métricas
    views_count = Column(Integer, default=0)
    clicks_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    product = relationship("Product", back_populates="publications")
    template = relationship("Template", back_populates="publications")
    interactions = relationship("UserInteraction", back_populates="publication")
    
    def __repr__(self):
        return f"<Publication {self.id} - Product:{self.product_id}>"


class UserInteraction(Base):
    """Modelo de interação do usuário"""
    __tablename__ = "user_interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=True)
    
    # Tipo de interação
    interaction_type = Column(String(50), nullable=False)  # view, click_buy, activate_alert, deactivate_alert, etc.
    
    # Dados adicionais
    interaction_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    user = relationship("User", back_populates="interactions")
    product = relationship("Product", back_populates="interactions")
    publication = relationship("Publication", back_populates="interactions")
    
    def __repr__(self):
        return f"<Interaction {self.interaction_type} - User:{self.user_id}>"


class SourceTracking(Base):
    """Modelo de rastreamento de origem"""
    __tablename__ = "source_tracking"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    # Origem
    source_type = Column(String(50), nullable=False)  # channel, deep_link, referral, etc.
    source_id = Column(String(255), nullable=True)
    product_code = Column(String(50), nullable=True)
    
    # Metadados
    tracking_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    user = relationship("User", back_populates="source_tracking")
    
    def __repr__(self):
        return f"<SourceTracking {self.source_type} - User:{self.user_id}>"


class ButtonConfig(Base):
    """Modelo de configuração de botões"""
    __tablename__ = "button_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    text = Column(String(255), nullable=False)
    emoji = Column(String(10), nullable=True)
    
    # Configuração do botão
    action_type = Column(String(50), nullable=False)  # callback, url, deep_link, etc.
    action_data = Column(JSON, nullable=True)
    url = Column(String(1000), nullable=True)
    callback_data = Column(String(500), nullable=True)
    
    # Posição
    position = Column(Integer, default=0)
    row = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ButtonConfig {self.name} - {self.text}>"


class Schedule(Base):
    """Modelo de agendamento"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    
    # Configuração de agendamento
    schedule_type = Column(String(50), nullable=False)  # daily, weekly, custom
    days_of_week = Column(JSON, nullable=True)
    times = Column(JSON, nullable=True)
    
    # Relacionamento com produtos/categorias
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Schedule {self.name} - {self.schedule_type}>"


class AdminLog(Base):
    """Modelo de log administrativo"""
    __tablename__ = "admin_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AdminLog {self.action} - Admin:{self.admin_id}>"
