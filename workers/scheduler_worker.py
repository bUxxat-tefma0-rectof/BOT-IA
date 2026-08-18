"""
Worker de agendamento de publicações
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from aiogram import Bot
import pytz

from database.session import db_manager
from database.models import Product, Publication, Schedule, OfferStatus
from services.publication_service import PublicationService
from services.product_service import ProductService
from redis_manager import redis_manager
from config import settings


class SchedulerWorker:
    """
    Worker para gerenciar publicações agendadas
    """
    
    def __init__(self, bot: Bot, publication_service: PublicationService):
        self.bot = bot
        self.publication_service = publication_service
        self.product_service = ProductService()
        self.is_running = False
        self.check_interval = 30
        self.timezone = pytz.timezone(settings.TIMEZONE)
        
    async def start(self):
        """Inicia o worker"""
        logger.info("Starting scheduler worker")
        self.is_running = True
        
        while self.is_running:
            try:
                await self.process_scheduled_publications()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in scheduler worker: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Para o worker"""
        logger.info("Stopping scheduler worker")
        self.is_running = False
    
    async def process_scheduled_publications(self):
        """Processa publicações agendadas"""
        try:
            scheduled = await self.publication_service.get_scheduled_publications()
            now = datetime.utcnow()
            
            for publication in scheduled:
                if publication.scheduled_at and publication.scheduled_at <= now:
                    await self.publication_service.publish_product_to_channel(
                        bot=self.bot,
                        product_id=publication.product_id,
                        template_id=publication.template_id
                    )
                    
                    async with db_manager.get_session() as session:
                        pub = await session.get(Publication, publication.id)
                        if pub:
                            pub.status = OfferStatus.PUBLISHED
                            pub.published_at = datetime.utcnow()
                            pub.updated_at = datetime.utcnow()
                            await session.commit()
                    
                    logger.info(f"Publication {publication.id} published")
                    
        except Exception as e:
            logger.error(f"Error processing scheduled publications: {e}")
