"""
Serviço de análise e estatísticas
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_, extract
from loguru import logger

from database.session import db_manager
from database.models import (
    User, Product, Category, Alert, Publication,
    UserInteraction, SourceTracking, AlertStatus,
    OfferStatus, UserStatus
)
from redis_manager import redis_manager


class AnalyticsService:
    """Serviço para análise de dados e estatísticas"""
    
    def __init__(self):
        self.cache_prefix = "analytics:"
        self.cache_ttl = 300  # 5 minutos
    
    async def get_general_statistics(self) -> Dict[str, Any]:
        """Busca estatísticas gerais do sistema"""
        try:
            # Tentar cache
            cache_key = f"{self.cache_prefix}general"
            cached = await redis_manager.get_cache(cache_key)
            
            if cached:
                return cached
            
            async with db_manager.get_session_no_commit() as session:
                # Usuários
                total_users = await session.scalar(
                    select(func.count(User.id))
                )
                
                active_users = await session.scalar(
                    select(func.count(User.id))
                    .where(User.status == UserStatus.ACTIVE)
                )
                
                # Produtos
                total_products = await session.scalar(
                    select(func.count(Product.id))
                )
                
                active_products = await session.scalar(
                    select(func.count(Product.id))
                    .where(Product.status == OfferStatus.PUBLISHED)
                )
                
                published_products = await session.scalar(
                    select(func.count(Product.id))
                    .where(Product.status == OfferStatus.PUBLISHED)
                )
                
                # Interações
                total_views = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.interaction_type == 'view_product')
                )
                
                buy_clicks = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.interaction_type == 'click_buy')
                )
                
                alert_activations = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.interaction_type == 'activate_alert')
                )
                
                # Produto mais visto
                most_viewed_result = await session.execute(
                    select(Product.name, func.count(UserInteraction.id).label('views'))
                    .join(UserInteraction, UserInteraction.product_id == Product.id)
                    .where(UserInteraction.interaction_type == 'view_product')
                    .group_by(Product.id, Product.name)
                    .order_by(func.count(UserInteraction.id).desc())
                    .limit(1)
                )
                most_viewed = most_viewed_result.first()
                
                # Categoria mais acessada
                most_accessed_result = await session.execute(
                    select(Category.name, func.count(UserInteraction.id).label('accesses'))
                    .join(Product, Product.category_id == Category.id)
                    .join(UserInteraction, UserInteraction.product_id == Product.id)
                    .group_by(Category.id, Category.name)
                    .order_by(func.count(UserInteraction.id).desc())
                    .limit(1)
                )
                most_accessed = most_accessed_result.first()
                
                stats = {
                    'total_users': total_users or 0,
                    'active_users': active_users or 0,
                    'total_products': total_products or 0,
                    'active_products': active_products or 0,
                    'published_products': published_products or 0,
                    'total_views': total_views or 0,
                    'buy_clicks': buy_clicks or 0,
                    'alert_activations': alert_activations or 0,
                    'most_viewed_product': most_viewed[0] if most_viewed else "N/A",
                    'most_accessed_category': most_accessed[0] if most_accessed else "N/A"
                }
                
                # Cachear estatísticas
                await redis_manager.set_cache(cache_key, stats, self.cache_ttl)
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting general statistics: {e}")
            return {}
    
    async def get_product_statistics(self, product_id: int) -> Dict[str, Any]:
        """Busca estatísticas detalhadas de um produto"""
        try:
            async with db_manager.get_session_no_commit() as session:
                # Visualizações
                views_count = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.product_id == product_id)
                    .where(UserInteraction.interaction_type == 'view_product')
                )
                
                # Cliques em comprar
                buy_clicks = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.product_id == product_id)
                    .where(UserInteraction.interaction_type == 'click_buy')
                )
                
                # Alertas ativos
                active_alerts = await session.scalar(
                    select(func.count(Alert.id))
                    .where(Alert.product_id == product_id)
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                
                # Origem dos acessos
                sources_result = await session.execute(
                    select(SourceTracking.source_type, func.count(SourceTracking.id))
                    .where(SourceTracking.product_code == str(product_id))
                    .group_by(SourceTracking.source_type)
                )
                sources = dict(sources_result.all())
                
                # Interações por hora
                hourly_result = await session.execute(
                    select(extract('hour', UserInteraction.created_at), func.count(UserInteraction.id))
                    .where(UserInteraction.product_id == product_id)
                    .group_by(extract('hour', UserInteraction.created_at))
                    .order_by(extract('hour', UserInteraction.created_at))
                )
                hourly_interactions = dict(hourly_result.all())
                
                return {
                    'product_id': product_id,
                    'views_count': views_count or 0,
                    'buy_clicks': buy_clicks or 0,
                    'active_alerts': active_alerts or 0,
                    'conversion_rate': ((buy_clicks or 0) / (views_count or 1)) * 100,
                    'sources': sources,
                    'hourly_interactions': hourly_interactions
                }
                
        except Exception as e:
            logger.error(f"Error getting product statistics: {e}")
            return {}
    
    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Busca estatísticas de um usuário"""
        try:
            async with db_manager.get_session_no_commit() as session:
                # Total de interações
                total_interactions = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.user_id == user_id)
                )
                
                # Produtos visualizados
                products_viewed = await session.scalar(
                    select(func.count(func.distinct(UserInteraction.product_id)))
                    .where(UserInteraction.user_id == user_id)
                    .where(UserInteraction.interaction_type == 'view_product')
                )
                
                # Alertas ativos
                active_alerts = await session.scalar(
                    select(func.count(Alert.id))
                    .where(Alert.user_id == user_id)
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                
                # Compras (cliques em comprar)
                buy_clicks = await session.scalar(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.user_id == user_id)
                    .where(UserInteraction.interaction_type == 'click_buy')
                )
                
                return {
                    'user_id': user_id,
                    'total_interactions': total_interactions or 0,
                    'products_viewed': products_viewed or 0,
                    'active_alerts': active_alerts or 0,
                    'buy_clicks': buy_clicks or 0
                }
                
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {}
    
    async def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """Gera relatório de performance dos últimos N dias"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            async with db_manager.get_session_no_commit() as session:
                # Interações por dia
                daily_interactions = await session.execute(
                    select(
                        func.date(UserInteraction.created_at).label('date'),
                        func.count(UserInteraction.id).label('count')
                    )
                    .where(UserInteraction.created_at >= start_date)
                    .group_by(func.date(UserInteraction.created_at))
                    .order_by(func.date(UserInteraction.created_at))
                )
                
                # Novos usuários por dia
                daily_users = await session.execute(
                    select(
                        func.date(User.created_at).label('date'),
                        func.count(User.id).label('count')
                    )
                    .where(User.created_at >= start_date)
                    .group_by(func.date(User.created_at))
                    .order_by(func.date(User.created_at))
                )
                
                # Top produtos
                top_products = await session.execute(
                    select(
                        Product.name,
                        func.count(UserInteraction.id).label('interactions')
                    )
                    .join(UserInteraction, UserInteraction.product_id == Product.id)
                    .where(UserInteraction.created_at >= start_date)
                    .group_by(Product.id, Product.name)
                    .order_by(func.count(UserInteraction.id).desc())
                    .limit(10)
                )
                
                return {
                    'period_days': days,
                    'daily_interactions': [
                        {'date': str(row[0]), 'count': row[1]} 
                        for row in daily_interactions
                    ],
                    'daily_users': [
                        {'date': str(row[0]), 'count': row[1]} 
                        for row in daily_users
                    ],
                    'top_products': [
                        {'name': row[0], 'interactions': row[1]} 
                        for row in top_products
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error getting performance report: {e}")
            return {}
