"""
Serviço de monitoramento de preços
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update
from loguru import logger
import asyncio
import aiohttp
import json

from database.session import db_manager
from database.models import Product, Alert, AlertStatus, OfferStatus
from services.alert_service import AlertService
from redis_manager import redis_manager


class MonitoringService:
    """
    Serviço para monitoramento de preços
    Utiliza APIs oficiais e fontes confiáveis
    """
    
    def __init__(self):
        self.alert_service = AlertService()
        self.monitoring_interval = 3600  # 1 hora em segundos
        self.api_timeout = 30  # 30 segundos
        self.cache_prefix = "monitoring:"
        self.cache_ttl = 3600
    
    async def start_monitoring(self):
        """Inicia o loop de monitoramento"""
        logger.info("Starting price monitoring service")
        
        while True:
            try:
                await self.check_all_monitored_products()
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto em caso de erro
    
    async def check_all_monitored_products(self):
        """Verifica todos os produtos monitorados"""
        try:
            # Buscar produtos com monitoramento ativo
            products = await self.get_monitored_products()
            
            logger.info(f"Checking {len(products)} monitored products")
            
            for product in products:
                try:
                    await self.check_product_price(product)
                    await asyncio.sleep(2)  # Delay entre verificações
                    
                except Exception as e:
                    logger.error(f"Error checking product {product.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking all monitored products: {e}")
    
    async def get_monitored_products(self) -> List[Product]:
        """Busca produtos com monitoramento ativo"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .where(Product.is_monitoring == True)
                    .where(Product.status == OfferStatus.PUBLISHED)
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error getting monitored products: {e}")
            return []
    
    async def check_product_price(self, product: Product):
        """
        Verifica preço atual de um produto
        
        Args:
            product: Produto a ser verificado
        """
        try:
            # Verificar se há link para monitoramento
            if not product.shopee_link:
                logger.warning(f"Product {product.id} has no Shopee link for monitoring")
                return
            
            # Buscar preço atual (usando API oficial)
            current_price = await self.fetch_product_price(product)
            
            if current_price is None:
                logger.warning(f"Could not fetch price for product {product.id}")
                return
            
            # Comparar com preço armazenado
            if product.current_price and current_price != product.current_price:
                old_price = product.current_price
                
                logger.info(f"Price changed for product {product.id}: {old_price} -> {current_price}")
                
                # Atualizar preço no banco
                await self.update_product_price(product.id, current_price)
                
                # Verificar condições de alerta
                await self.check_alert_conditions(product, old_price, current_price)
                
        except Exception as e:
            logger.error(f"Error checking product price: {e}")
    
    async def fetch_product_price(self, product: Product) -> Optional[float]:
        """
        Busca preço atual do produto na Shopee
        Utiliza API oficial quando disponível
        """
        try:
            # Verificar cache primeiro
            cache_key = f"{self.cache_prefix}price:{product.id}"
            cached_price = await redis_manager.get_cache(cache_key)
            
            if cached_price is not None:
                return cached_price
            
            # Simulação de busca de preço
            # TODO: Integrar com API oficial da Shopee
            # Por enquanto, simular verificação
            current_price = product.current_price
            
            # Cachear resultado
            await redis_manager.set_cache(cache_key, current_price, self.cache_ttl)
            
            return current_price
            
        except Exception as e:
            logger.error(f"Error fetching product price: {e}")
            return None
    
    async def update_product_price(self, product_id: int, new_price: float):
        """Atualiza preço do produto no banco"""
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
                    
                    logger.info(f"Product {product_id} price updated to {new_price}")
                    
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
    
    async def check_alert_conditions(self, product: Product, old_price: float, new_price: float):
        """
        Verifica condições de alerta após mudança de preço
        
        Args:
            product: Produto monitorado
            old_price: Preço anterior
            new_price: Novo preço
        """
        try:
            # Verificar queda de preço
            if new_price < old_price:
                await self.alert_service.trigger_alerts_for_price_drop(
                    product.id,
                    old_price,
                    new_price
                )
            
            # Verificar preço alvo
            if product.target_price and new_price <= product.target_price:
                await self.alert_service.trigger_alerts_for_price_target(
                    product.id,
                    new_price,
                    product.target_price
                )
                
        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
    
    async def configure_monitoring(self, product_id: int, config: Dict[str, Any]) -> bool:
        """
        Configura monitoramento para um produto
        
        Args:
            product_id: ID do produto
            config: Configurações de monitoramento
        
        Returns:
            bool: True se sucesso
        """
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                
                if not product:
                    return False
                
                product.is_monitoring = config.get('is_monitoring', True)
                product.monitoring_config = config.get('conditions', {})
                product.updated_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(f"Monitoring configured for product {product_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error configuring monitoring: {e}")
            return False
    
    async def get_monitoring_status(self, product_id: int) -> Dict[str, Any]:
        """Busca status de monitoramento de um produto"""
        try:
            async with db_manager.get_session_no_commit() as session:
                product = await session.get(Product, product_id)
                
                if not product:
                    return {}
                
                return {
                    'product_id': product.id,
                    'is_monitoring': product.is_monitoring,
                    'current_price': product.current_price,
                    'target_price': product.target_price,
                    'monitoring_config': product.monitoring_config,
                    'last_updated': product.updated_at
                }
                
        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {}
