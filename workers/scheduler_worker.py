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
        self.check_interval = 30  # Verificar a cada 30 segundos
        self.timezone = pytz.timezone(settings.TIMEZONE)
        
    async def start(self):
        """Inicia o worker de agendamento"""
        logger.info("Starting scheduler worker")
        self.is_running = True
        
        while self.is_running:
            try:
                await self.process_scheduled_publications()
                await self.process_automatic_schedules()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in scheduler worker: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Para o worker de agendamento"""
        logger.info("Stopping scheduler worker")
        self.is_running = False
    
    async def process_scheduled_publications(self):
        """Processa publicações agendadas"""
        try:
            # Buscar publicações agendadas
            scheduled = await self.publication_service.get_scheduled_publications()
            
            now = datetime.utcnow()
            
            for publication in scheduled:
                if publication.scheduled_at and publication.scheduled_at <= now:
                    # Publicar no canal
                    logger.info(f"Publishing scheduled product {publication.product_id}")
                    
                    await self.publication_service.publish_product_to_channel(
                        bot=self.bot,
                        product_id=publication.product_id,
                        template_id=publication.template_id
                    )
                    
                    # Atualizar status
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
    
    async def process_automatic_schedules(self):
        """Processa rotinas automáticas de publicação"""
        try:
            # Buscar rotinas ativas
            async with db_manager.get_session_no_commit() as session:
                from sqlalchemy import select
                
                result = await session.execute(
                    select(Schedule)
                    .where(Schedule.is_active == True)
                )
                schedules = result.scalars().all()
                
                now = datetime.now(self.timezone)
                
                for schedule in schedules:
                    if await self.should_run_schedule(schedule, now):
                        await self.execute_schedule(schedule)
                        
        except Exception as e:
            logger.error(f"Error processing automatic schedules: {e}")
    
    async def should_run_schedule(self, schedule: Schedule, current_time: datetime) -> bool:
        """
        Verifica se uma rotina deve ser executada
        
        Args:
            schedule: Rotina a verificar
            current_time: Hora atual
        
        Returns:
            bool: True se deve executar
        """
        try:
            # Verificar dias da semana
            if schedule.days_of_week:
                current_day = current_time.weekday()
                if current_day not in schedule.days_of_week:
                    return False
            
            # Verificar horários
            if schedule.times:
                current_hour = current_time.hour
                current_minute = current_time.minute
                
                for time_str in schedule.times:
                    try:
                        target_hour, target_minute = map(int, time_str.split(':'))
                        
                        if current_hour == target_hour and current_minute == target_minute:
                            # Verificar se já executou nesta hora
                            cache_key = f"schedule_executed:{schedule.id}:{time_str}"
                            executed = await redis_manager.get_cache(cache_key)
                            
                            if not executed:
                                # Marcar como executado
                                await redis_manager.set_cache(cache_key, True, 3600)
                                return True
                    
                    except:
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking schedule: {e}")
            return False
    
    async def execute_schedule(self, schedule: Schedule):
        """Executa uma rotina de publicação"""
        try:
            # Buscar produtos para publicar
            products = []
            
            if schedule.product_id:
                # Produto específico
                product = await self.product_service.get_product_by_id(schedule.product_id)
                if product:
                    products.append(product)
            elif schedule.category_id:
                # Produtos de uma categoria
                products = await self.product_service.get_products_by_category(
                    schedule.category_id,
                    limit=5
                )
            else:
                # Ofertas ativas
                products = await self.product_service.get_active_offers(limit=5)
            
            # Publicar produtos
            for product in products:
                await self.publication_service.publish_product_to_channel(
                    bot=self.bot,
                    product_id=product.id
                )
                await asyncio.sleep(5)  # Delay entre publicações
                
            logger.info(f"Schedule {schedule.id} executed")
            
        except Exception as e:
            logger.error(f"Error executing schedule: {e}")
    
    async def create_schedule(self, schedule_data: Dict[str, Any]) -> Optional[Schedule]:
        """Cria nova rotina de agendamento"""
        try:
            async with db_manager.get_session() as session:
                schedule = Schedule(
                    name=schedule_data.get('name'),
                    schedule_type=schedule_data.get('schedule_type', 'daily'),
                    days_of_week=schedule_data.get('days_of_week'),
                    times=schedule_data.get('times'),
                    product_id=schedule_data.get('product_id'),
                    category_id=schedule_data.get('category_id'),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(schedule)
                await session.commit()
                
                logger.info(f"Schedule created: {schedule.name}")
                return schedule
                
        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return None
    
    async def get_schedules(self) -> List[Schedule]:
        """Busca todas as rotinas"""
        try:
            from sqlalchemy import select
            
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Schedule)
                    .order_by(Schedule.created_at.desc())
                )
                schedules = result.scalars().all()
                
                return list(schedules)
                
        except Exception as e:
            logger.error(f"Error getting schedules: {e}")
            return []
    
    async def delete_schedule(self, schedule_id: int) -> bool:
        """Remove uma rotina"""
        try:
            async with db_manager.get_session() as session:
                schedule = await session.get(Schedule, schedule_id)
                
                if not schedule:
                    return False
                
                schedule.is_active = False
                schedule.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Schedule {schedule_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting schedule: {e}")
            return False
