"""
Worker de monitoramento de preços
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from aiogram import Bot

from database.session import db_manager
from database.models import Product, Alert, AlertStatus, OfferStatus
from services.alert_service import AlertService
from services.monitoring_service import MonitoringService
from redis_manager import redis_manager
from config import settings


class MonitoringWorker:
    """
    Worker para monitoramento contínuo de preços
    """
    
    def __init__(self, bot: Bot, alert_service: AlertService):
        self.bot = bot
        self.alert_service = alert_service
        self.monitoring_service = MonitoringService()
        self.is_running = False
        self.check_interval = 3600
        self.error_retry_interval = 300
        
    async def start(self):
        """Inicia o worker"""
        logger.info("Starting monitoring worker")
        self.is_running = True
        
        while self.is_running:
            try:
                await self.monitor_all_products()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring worker: {e}")
                await asyncio.sleep(self.error_retry_interval)
    
    async def stop(self):
        """Para o worker"""
        logger.info("Stopping monitoring worker")
        self.is_running = False
    
    async def monitor_all_products(self):
        """Monitora todos os produtos ativos"""
        try:
            products = await self.monitoring_service.get_monitored_products()
            logger.info(f"Monitoring {len(products)} products")
            
            for product in products:
                try:
                    await self.monitor_product(product)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error monitoring product {product.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in monitor_all_products: {e}")
    
    async def monitor_product(self, product: Product):
        """Monitora um produto específico"""
        try:
            if not product.shopee_link:
                return
            
            current_price = await self.fetch_current_price(product)
            
            if current_price is None:
                return
            
            if product.current_price and current_price != product.current_price:
                old_price = product.current_price
                
                await self.update_product_price(product.id, current_price)
                await self.check_alert_conditions(product, old_price, current_price)
                
            if product.target_price and current_price <= product.target_price:
                await self.alert_service.trigger_alerts_for_price_target(
                    product.id,
                    current_price,
                    product.target_price
                )
                
        except Exception as e:
            logger.error(f"Error monitoring product {product.id}: {e}")
    
    async def fetch_current_price(self, product: Product) -> Optional[float]:
        """Busca preço atual do produto"""
        try:
            cache_key = f"price_cache:{product.id}"
            cached_price = await redis_manager.get_cache(cache_key)
            
            if cached_price is not None:
                return cached_price
            
            current_price = product.current_price
            await redis_manager.set_cache(cache_key, current_price, 1800)
            
            return current_price
            
        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            return None
    
    async def update_product_price(self, product_id: int, new_price: float):
        """Atualiza preço do produto"""
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                
                if product:
                    product.current_price = new_price
                    
                    if product.original_price and product.original_price > 0:
                        discount = ((product.original_price - new_price) / product.original_price) * 100
                        product.discount_percentage = discount
                    
                    product.updated_at = datetime.utcnow()
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
    
    async def check_alert_conditions(self, product: Product, old_price: float, new_price: float):
        """Verifica condições de alerta"""
        try:
            if new_price < old_price:
                await self.alert_service.trigger_alerts_for_price_drop(
                    product.id,
                    old_price,
                    new_price
                )
            
            if product.target_price and new_price <= product.target_price:
                await self.alert_service.trigger_alerts_for_price_target(
                    product.id,
                    new_price,
                    product.target_price
                )
                
        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
