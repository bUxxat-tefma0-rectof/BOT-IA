"""
Worker de monitoramento de preços
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from aiogram import Bot
import aiohttp
import json

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
        self.check_interval = 3600  # Verificar a cada 1 hora
        self.error_retry_interval = 300  # 5 minutos em caso de erro
        
    async def start(self):
        """Inicia o worker de monitoramento"""
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
        """Para o worker de monitoramento"""
        logger.info("Stopping monitoring worker")
        self.is_running = False
    
    async def monitor_all_products(self):
        """Monitora todos os produtos ativos"""
        try:
            # Buscar produtos monitorados
            products = await self.monitoring_service.get_monitored_products()
            
            logger.info(f"Monitoring {len(products)} products")
            
            for product in products:
                try:
                    await self.monitor_product(product)
                    await asyncio.sleep(2)  # Delay entre verificações
                    
                except Exception as e:
                    logger.error(f"Error monitoring product {product.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in monitor_all_products: {e}")
    
    async def monitor_product(self, product: Product):
        """Monitora um produto específico"""
        try:
            # Verificar se o produto tem link válido
            if not product.shopee_link:
                logger.warning(f"Product {product.id} has no valid link")
                return
            
            # Buscar preço atual
            current_price = await self.fetch_current_price(product)
            
            if current_price is None:
                logger.warning(f"Could not fetch price for product {product.id}")
                return
            
            # Verificar mudança de preço
            if product.current_price and current_price != product.current_price:
                old_price = product.current_price
                
                logger.info(f"Price changed for product {product.id}: {old_price} -> {current_price}")
                
                # Atualizar preço no banco
                await self.update_product_price(product.id, current_price)
                
                # Verificar condições de alerta
                await self.check_alert_conditions(product, old_price, current_price)
                
            # Verificar preço alvo
            if product.target_price and current_price <= product.target_price:
                await self.alert_service.trigger_alerts_for_price_target(
                    product.id,
                    current_price,
                    product.target_price
                )
                
            # Atualizar timestamp de monitoramento
            await self.update_monitoring_timestamp(product.id)
            
        except Exception as e:
            logger.error(f"Error monitoring product {product.id}: {e}")
    
    async def fetch_current_price(self, product: Product) -> Optional[float]:
        """
        Busca preço atual do produto
        
        Args:
            product: Produto a verificar
        
        Returns:
            float: Preço atual ou None se erro
        """
        try:
            # Verificar cache
            cache_key = f"price_cache:{product.id}"
            cached_price = await redis_manager.get_cache(cache_key)
            
            if cached_price is not None:
                return cached_price
            
            # Tentar buscar da API da Shopee
            # TODO: Integrar com API oficial
            # Por enquanto, simular verificação
            current_price = product.current_price
            
            # Cachear resultado
            await redis_manager.set_cache(cache_key, current_price, 1800)  # 30 minutos
            
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
                    
                    # Recalcular desconto
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
            # Queda de preço
            if new_price < old_price:
                await self.alert_service.trigger_alerts_for_price_drop(
                    product.id,
                    old_price,
                    new_price
                )
            
            # Preço alvo atingido
            if product.target_price and new_price <= product.target_price:
                await self.alert_service.trigger_alerts_for_price_target(
                    product.id,
                    new_price,
                    product.target_price
                )
                
        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
    
    async def update_monitoring_timestamp(self, product_id: int):
        """Atualiza timestamp de monitoramento"""
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                
                if product:
                    if not product.monitoring_config:
                        product.monitoring_config = {}
                    
                    product.monitoring_config['last_checked'] = datetime.utcnow().isoformat()
                    product.updated_at = datetime.utcnow()
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error updating monitoring timestamp: {e}")
    
    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """Busca estatísticas de monitoramento"""
        try:
            async with db_manager.get_session_no_commit() as session:
                from sqlalchemy import select, func
                
                # Total de produtos monitorados
                total_monitored = await session.scalar(
                    select(func.count(Product.id))
                    .where(Product.is_monitoring == True)
                )
                
                # Produtos com alertas ativos
                products_with_alerts = await session.scalar(
                    select(func.count(func.distinct(Alert.product_id)))
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                
                # Total de alertas ativos
                total_alerts = await session.scalar(
                    select(func.count(Alert.id))
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                
                return {
                    'total_monitored': total_monitored or 0,
                    'products_with_alerts': products_with_alerts or 0,
                    'total_alerts': total_alerts or 0,
                    'last_check': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting monitoring stats: {e}")
            return {}
