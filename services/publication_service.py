"""
Serviço de publicações no canal
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
from loguru import logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot

from database.session import db_manager
from database.models import (
    Product, Publication, Template, Category,
    OfferStatus, UserInteraction
)
from services.product_service import ProductService
from redis_manager import redis_manager
from config import settings


class PublicationService:
    """Serviço para gerenciamento de publicações no canal"""
    
    def __init__(self):
        self.product_service = ProductService()
        self.cache_prefix = "publication:"
        self.cache_ttl = 3600
    
    async def publish_product_to_channel(self, bot: Bot, product_id: int, template_id: int = None) -> Optional[Publication]:
        """
        Publica produto no canal
        
        Args:
            bot: Instância do bot
            product_id: ID do produto
            template_id: ID do template (opcional)
        
        Returns:
            Publication: Publicação criada ou None se erro
        """
        try:
            # Buscar produto
            product = await self.product_service.get_product_by_id(product_id)
            
            if not product:
                logger.error(f"Product {product_id} not found for publication")
                return None
            
            # Preparar texto da publicação
            publication_text = await self.format_publication_text(product)
            
            # Preparar botões
            keyboard = await self.create_publication_keyboard(product)
            
            # Publicar no canal
            channel_id = settings.CHANNEL_ID
            
            try:
                if product.image_url:
                    # Publicar com imagem
                    sent_message = await bot.send_photo(
                        chat_id=channel_id,
                        photo=product.image_url,
                        caption=publication_text,
                        reply_markup=keyboard
                    )
                else:
                    # Publicar sem imagem
                    sent_message = await bot.send_message(
                        chat_id=channel_id,
                        text=publication_text,
                        reply_markup=keyboard
                    )
                
                # Criar registro de publicação
                async with db_manager.get_session() as session:
                    publication = Publication(
                        product_id=product_id,
                        template_id=template_id,
                        channel_message_id=sent_message.message_id,
                        message_text=publication_text,
                        status=OfferStatus.PUBLISHED,
                        published_at=datetime.utcnow(),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    session.add(publication)
                    
                    # Atualizar status do produto
                    product.status = OfferStatus.PUBLISHED
                    product.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    
                    logger.info(f"Product {product.product_code} published to channel")
                    return publication
                    
            except Exception as e:
                logger.error(f"Error sending message to channel: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error publishing product to channel: {e}")
            return None
    
    async def format_publication_text(self, product: Product) -> str:
        """Formata texto da publicação"""
        try:
            text_parts = []
            
            # Título com emoji de oferta
            text_parts.append("🔥 <b>OFERTA TECNOLÓGICA</b>")
            text_parts.append("")
            
            # Nome do produto
            text_parts.append(f"📦 <b>{product.name}</b>")
            text_parts.append("")
            
            # Preços
            if product.original_price and product.current_price:
                text_parts.append(f"💰 <b>De:</b> R$ {product.original_price:.2f}")
                text_parts.append(f"🔥 <b>Por:</b> R$ {product.current_price:.2f}")
                
                if product.discount_percentage:
                    text_parts.append(f"📊 <b>Desconto:</b> {product.discount_percentage:.0f}%")
            else:
                text_parts.append(f"💰 <b>Preço:</b> R$ {product.current_price:.2f}")
            
            # Descrição
            if product.description:
                text_parts.append("")
                text_parts.append("📝 <b>Descrição:</b>")
                text_parts.append(product.description)
            
            # Código
            text_parts.append("")
            text_parts.append(f"🆔 <b>Código:</b> {product.product_code}")
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Error formatting publication text: {e}")
            return f"📦 {product.name}\n\n💰 R$ {product.current_price:.2f}"
    
    async def create_publication_keyboard(self, product: Product) -> InlineKeyboardMarkup:
        """Cria teclado da publicação no canal"""
        try:
            keyboard = []
            
            # Botão de ativar promoção
            keyboard.append([
                InlineKeyboardButton(
                    text="⚪ ATIVAR PROMOÇÃO",
                    callback_data=f"activate_promotion_{product.id}"
                )
            ])
            
            # Botão de ir para oferta (deeplink)
            keyboard.append([
                InlineKeyboardButton(
                    text="🛒 IR PARA OFERTA",
                    url=f"https://t.me/{(await self.get_bot_username())}?start=oferta_{product.product_code}"
                )
            ])
            
            # Botão de suporte
            keyboard.append([
                InlineKeyboardButton(
                    text="💬 SUPORTE",
                    url="https://t.me/techoffers_suporte"
                )
            ])
            
            return InlineKeyboardMarkup(inline_keyboard=keyboard)
            
        except Exception as e:
            logger.error(f"Error creating publication keyboard: {e}")
            return None
    
    async def get_bot_username(self) -> str:
        """Busca username do bot"""
        try:
            from bot.main import TechOffersBot
            bot_app = TechOffersBot()
            bot_info = await bot_app.bot.get_me()
            return bot_info.username
        except:
            return "TechOffersBot"
    
    async def edit_publication_message(self, bot: Bot, publication_id: int, new_text: str = None, new_keyboard: InlineKeyboardMarkup = None) -> bool:
        """
        Edita mensagem de publicação no canal
        
        Args:
            bot: Instância do bot
            publication_id: ID da publicação
            new_text: Novo texto (opcional)
            new_keyboard: Novo teclado (opcional)
        
        Returns:
            bool: True se sucesso
        """
        try:
            async with db_manager.get_session_no_commit() as session:
                publication = await session.get(Publication, publication_id)
                
                if not publication:
                    return False
                
                channel_id = settings.CHANNEL_ID
                
                if new_text and new_keyboard:
                    await bot.edit_message_text(
                        chat_id=channel_id,
                        message_id=publication.channel_message_id,
                        text=new_text,
                        reply_markup=new_keyboard
                    )
                elif new_text:
                    await bot.edit_message_text(
                        chat_id=channel_id,
                        message_id=publication.channel_message_id,
                        text=new_text
                    )
                elif new_keyboard:
                    await bot.edit_message_reply_markup(
                        chat_id=channel_id,
                        message_id=publication.channel_message_id,
                        reply_markup=new_keyboard
                    )
                
                return True
                
        except Exception as e:
            logger.error(f"Error editing publication message: {e}")
            return False
    
    async def delete_publication(self, bot: Bot, publication_id: int) -> bool:
        """Remove publicação do canal"""
        try:
            async with db_manager.get_session() as session:
                publication = await session.get(Publication, publication_id)
                
                if not publication:
                    return False
                
                channel_id = settings.CHANNEL_ID
                
                # Tentar remover mensagem
                try:
                    await bot.delete_message(
                        chat_id=channel_id,
                        message_id=publication.channel_message_id
                    )
                except:
                    logger.warning(f"Could not delete message {publication.channel_message_id}")
                
                # Atualizar status
                publication.status = OfferStatus.CANCELLED
                publication.updated_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(f"Publication {publication_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting publication: {e}")
            return False
    
    async def schedule_publication(self, product_id: int, scheduled_at: datetime, template_id: int = None) -> Optional[Publication]:
        """Agenda publicação para o futuro"""
        try:
            async with db_manager.get_session() as session:
                publication = Publication(
                    product_id=product_id,
                    template_id=template_id,
                    status=OfferStatus.SCHEDULED,
                    scheduled_at=scheduled_at,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(publication)
                await session.commit()
                
                logger.info(f"Publication scheduled for {scheduled_at}")
                return publication
                
        except Exception as e:
            logger.error(f"Error scheduling publication: {e}")
            return None
    
    async def get_scheduled_publications(self) -> List[Publication]:
        """Busca publicações agendadas"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Publication)
                    .where(Publication.status == OfferStatus.SCHEDULED)
                    .where(Publication.scheduled_at > datetime.utcnow())
                    .order_by(Publication.scheduled_at)
                )
                publications = result.scalars().all()
                
                return list(publications)
                
        except Exception as e:
            logger.error(f"Error getting scheduled publications: {e}")
            return []
    
    async def get_active_publications(self) -> List[Publication]:
        """Busca publicações ativas"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Publication)
                    .where(Publication.status == OfferStatus.PUBLISHED)
                    .order_by(Publication.published_at.desc())
                )
                publications = result.scalars().all()
                
                return list(publications)
                
        except Exception as e:
            logger.error(f"Error getting active publications: {e}")
            return []
    
    async def update_publication_metrics(self, publication_id: int, metric_type: str):
        """Atualiza métricas da publicação"""
        try:
            async with db_manager.get_session() as session:
                publication = await session.get(Publication, publication_id)
                
                if not publication:
                    return
                
                if metric_type == "view":
                    publication.views_count += 1
                elif metric_type == "click":
                    publication.clicks_count += 1
                
                publication.updated_at = datetime.utcnow()
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error updating publication metrics: {e}")
