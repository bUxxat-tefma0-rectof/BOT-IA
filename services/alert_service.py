"""
Serviço de gerenciamento de alertas
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_
from loguru import logger

from database.session import db_manager
from database.models import (
    User, Product, Alert, AlertStatus, 
    UserInteraction, Publication
)
from redis_manager import redis_manager


class AlertService:
    """Serviço para gerenciamento de alertas"""
    
    def __init__(self):
        self.cache_prefix = "alert:"
        self.cache_ttl = 1800  # 30 minutos
    
    async def toggle_alert(self, user_id: int, product_id: int) -> bool:
        """
        Ativa ou desativa alerta para um produto
        
        Args:
            user_id: ID do usuário
            product_id: ID do produto
        
        Returns:
            bool: True se sucesso, False se erro
        """
        try:
            async with db_manager.get_session() as session:
                # Verificar se alerta já existe
                result = await session.execute(
                    select(Alert)
                    .where(Alert.user_id == user_id)
                    .where(Alert.product_id == product_id)
                )
                existing_alert = result.scalar_one_or_none()
                
                if existing_alert:
                    # Alternar status
                    if existing_alert.status == AlertStatus.ACTIVE:
                        existing_alert.status = AlertStatus.INACTIVE
                        existing_alert.updated_at = datetime.utcnow()
                        logger.info(f"Alert deactivated: user={user_id}, product={product_id}")
                    else:
                        existing_alert.status = AlertStatus.ACTIVE
                        existing_alert.updated_at = datetime.utcnow()
                        logger.info(f"Alert activated: user={user_id}, product={product_id}")
                    
                    await session.commit()
                else:
                    # Criar novo alerta
                    alert = Alert(
                        user_id=user_id,
                        product_id=product_id,
                        status=AlertStatus.ACTIVE,
                        alert_conditions={
                            "notify_price_drop": True,
                            "notify_price_target": True,
                            "notify_new_promotion": True
                        },
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    session.add(alert)
                    await session.commit()
                    logger.info(f"Alert created: user={user_id}, product={product_id}")
                
                # Limpar cache
                await redis_manager.clear_cache_pattern(f"{self.cache_prefix}*")
                
                return True
                
        except Exception as e:
            logger.error(f"Error toggling alert: {e}")
            return False
    
    async def get_user_alerts(self, user_id: int, only_active: bool = False) -> List[Alert]:
        """Busca alertas de um usuário"""
        try:
            async with db_manager.get_session_no_commit() as session:
                query = select(Alert).where(Alert.user_id == user_id)
                
                if only_active:
                    query = query.where(Alert.status == AlertStatus.ACTIVE)
                
                query = query.order_by(Alert.created_at.desc())
                
                result = await session.execute(query)
                alerts = result.scalars().all()
                
                return list(alerts)
                
        except Exception as e:
            logger.error(f"Error getting user alerts: {e}")
            return []
    
    async def has_active_alert(self, user_id: int, product_id: int) -> bool:
        """Verifica se usuário tem alerta ativo para produto"""
        try:
            # Tentar cache
            cache_key = f"{self.cache_prefix}{user_id}:{product_id}"
            cached = await redis_manager.get_cache(cache_key)
            
            if cached is not None:
                return cached
            
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Alert)
                    .where(Alert.user_id == user_id)
                    .where(Alert.product_id == product_id)
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                alert = result.scalar_one_or_none()
                
                has_alert = alert is not None
                
                # Cachear resultado
                await redis_manager.set_cache(cache_key, has_alert, self.cache_ttl)
                
                return has_alert
                
        except Exception as e:
            logger.error(f"Error checking active alert: {e}")
            return False
    
    async def get_product_alert_users(self, product_id: int) -> List[int]:
        """Busca usuários com alerta ativo para um produto"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Alert.user_id)
                    .where(Alert.product_id == product_id)
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                user_ids = result.scalars().all()
                
                return list(user_ids)
                
        except Exception as e:
            logger.error(f"Error getting product alert users: {e}")
            return []
    
    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Busca estatísticas de alertas"""
        try:
            async with db_manager.get_session_no_commit() as session:
                # Total de alertas ativos
                active_result = await session.execute(
                    select(func.count(Alert.id))
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                active_alerts = active_result.scalar() or 0
                
                # Produtos monitorados
                products_result = await session.execute(
                    select(func.count(func.distinct(Alert.product_id)))
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                monitored_products = products_result.scalar() or 0
                
                # Usuários com alertas
                users_result = await session.execute(
                    select(func.count(func.distinct(Alert.user_id)))
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                users_with_alerts = users_result.scalar() or 0
                
                return {
                    'active_alerts': active_alerts,
                    'monitored_products': monitored_products,
                    'users_with_alerts': users_with_alerts
                }
                
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {
                'active_alerts': 0,
                'monitored_products': 0,
                'users_with_alerts': 0
            }
    
    async def trigger_alerts_for_price_drop(self, product_id: int, old_price: float, new_price: float):
        """Dispara alertas quando preço cai"""
        try:
            # Buscar usuários com alerta ativo
            user_ids = await self.get_product_alert_users(product_id)
            
            if not user_ids:
                return
            
            # Buscar produto
            from services.product_service import ProductService
            product_service = ProductService()
            product = await product_service.get_product_by_id(product_id)
            
            if not product:
                return
            
            # Calcular desconto
            discount = ((old_price - new_price) / old_price) * 100
            
            # Notificar usuários
            from bot.main import TechOffersBot
            bot_app = TechOffersBot()
            
            for user_id in user_ids:
                try:
                    notification_text = (
                        f"🔔 <b>ALERTA DE PREÇO!</b>\n\n"
                        f"📦 <b>Produto:</b> {product.name}\n"
                        f"💰 <b>Preço anterior:</b> R$ {old_price:.2f}\n"
                        f"🔥 <b>Novo preço:</b> R$ {new_price:.2f}\n"
                        f"📊 <b>Desconto:</b> {discount:.1f}%\n\n"
                        f"🛒 <a href='{product.shopee_link}'>COMPRAR AGORA</a>"
                    )
                    
                    await bot_app.bot.send_message(
                        chat_id=user_id,
                        text=notification_text
                    )
                    
                    logger.info(f"Alert sent to user {user_id} for product {product_id}")
                    
                except Exception as e:
                    logger.error(f"Error sending alert to user {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error triggering alerts for price drop: {e}")
    
    async def trigger_alerts_for_price_target(self, product_id: int, current_price: float, target_price: float):
        """Dispara alertas quando preço atinge alvo"""
        try:
            if current_price > target_price:
                return
            
            # Buscar usuários com alerta ativo
            user_ids = await self.get_product_alert_users(product_id)
            
            if not user_ids:
                return
            
            # Buscar produto
            from services.product_service import ProductService
            product_service = ProductService()
            product = await product_service.get_product_by_id(product_id)
            
            if not product:
                return
            
            # Notificar usuários
            from bot.main import TechOffersBot
            bot_app = TechOffersBot()
            
            for user_id in user_ids:
                try:
                    notification_text = (
                        f"🎯 <b>PREÇO ALVO ATINGIDO!</b>\n\n"
                        f"📦 <b>Produto:</b> {product.name}\n"
                        f"💰 <b>Preço atual:</b> R$ {current_price:.2f}\n"
                        f"🎯 <b>Preço alvo:</b> R$ {target_price:.2f}\n\n"
                        f"🛒 <a href='{product.shopee_link}'>COMPRAR AGORA</a>"
                    )
                    
                    await bot_app.bot.send_message(
                        chat_id=user_id,
                        text=notification_text
                    )
                    
                    # Atualizar alerta como disparado
                    async with db_manager.get_session() as session:
                        result = await session.execute(
                            select(Alert)
                            .where(Alert.user_id == user_id)
                            .where(Alert.product_id == product_id)
                        )
                        alert = result.scalar_one_or_none()
                        
                        if alert:
                            alert.status = AlertStatus.TRIGGERED
                            alert.triggered_at = datetime.utcnow()
                            await session.commit()
                    
                    logger.info(f"Target price alert sent to user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error sending target price alert: {e}")
                    
        except Exception as e:
            logger.error(f"Error triggering price target alerts: {e}")
