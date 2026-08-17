"""
Serviço de gerenciamento de produtos
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_
from loguru import logger

from database.session import db_manager
from database.models import (
    Product, Category, Alert, Publication, 
    UserInteraction, OfferStatus, AlertStatus
)
from redis_manager import redis_manager


class ProductService:
    """Serviço para gerenciamento de produtos"""
    
    def __init__(self):
        self.cache_prefix = "product:"
        self.cache_ttl = 3600  # 1 hora
    
    async def create_product(self, product_data: Dict[str, Any]) -> Optional[Product]:
        """
        Cria um novo produto
        
        Args:
            product_data: Dicionário com dados do produto
        
        Returns:
            Product: Produto criado ou None se erro
        """
        try:
            # Gerar código único
            import random
            product_code = f"#{random.randint(100, 999)}"
            
            async with db_manager.get_session() as session:
                product = Product(
                    product_code=product_code,
                    name=product_data.get('name'),
                    description=product_data.get('description'),
                    original_price=product_data.get('original_price'),
                    current_price=product_data.get('current_price'),
                    target_price=product_data.get('target_price'),
                    discount_percentage=product_data.get('discount_percentage'),
                    shopee_link=product_data.get('shopee_link'),
                    affiliate_link=product_data.get('affiliate_link'),
                    image_url=product_data.get('image_url'),
                    category_id=product_data.get('category_id'),
                    status=OfferStatus.DRAFT,
                    is_monitoring=product_data.get('is_monitoring', False),
                    monitoring_config=product_data.get('monitoring_config'),
                    start_date=product_data.get('start_date'),
                    end_date=product_data.get('end_date'),
                    template_id=product_data.get('template_id'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(product)
                await session.commit()
                
                # Limpar cache
                await redis_manager.clear_cache_pattern(f"{self.cache_prefix}*")
                
                logger.info(f"Product created: {product.product_code}")
                return product
                
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            return None
    
    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """Busca produto por ID"""
        try:
            # Tentar cache primeiro
            cache_key = f"{self.cache_prefix}{product_id}"
            cached = await redis_manager.get_cache(cache_key)
            
            if cached:
                return cached
            
            async with db_manager.get_session_no_commit() as session:
                product = await session.get(Product, product_id)
                
                if product:
                    # Cachear produto
                    await redis_manager.set_cache(cache_key, product, self.cache_ttl)
                
                return product
                
        except Exception as e:
            logger.error(f"Error getting product by ID: {e}")
            return None
    
    async def get_product_by_code(self, product_code: str) -> Optional[Product]:
        """Busca produto por código"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product).where(Product.product_code == product_code)
                )
                product = result.scalar_one_or_none()
                
                return product
                
        except Exception as e:
            logger.error(f"Error getting product by code: {e}")
            return None
    
    async def get_active_offers(self, limit: int = 10) -> List[Product]:
        """Busca ofertas ativas"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .where(Product.status == OfferStatus.PUBLISHED)
                    .where(or_(
                        Product.end_date.is_(None),
                        Product.end_date > datetime.utcnow()
                    ))
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error getting active offers: {e}")
            return []
    
    async def get_draft_products(self) -> List[Product]:
        """Busca produtos em rascunho"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .where(Product.status == OfferStatus.DRAFT)
                    .order_by(Product.created_at.desc())
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error getting draft products: {e}")
            return []
    
    async def get_products_by_category(self, category_id: int, limit: int = 10) -> List[Product]:
        """Busca produtos por categoria"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .where(Product.category_id == category_id)
                    .where(Product.status == OfferStatus.PUBLISHED)
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error getting products by category: {e}")
            return []
    
    async def update_product(self, product_id: int, update_data: Dict[str, Any]) -> bool:
        """Atualiza dados do produto"""
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                
                if not product:
                    return False
                
                # Atualizar campos
                for key, value in update_data.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                
                product.updated_at = datetime.utcnow()
                await session.commit()
                
                # Limpar cache
                cache_key = f"{self.cache_prefix}{product_id}"
                await redis_manager.delete_cache(cache_key)
                
                logger.info(f"Product updated: {product_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            return False
    
    async def delete_product(self, product_id: int) -> bool:
        """Remove produto"""
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                
                if not product:
                    return False
                
                # Verificar se há alertas ativos
                result = await session.execute(
                    select(Alert).where(
                        Alert.product_id == product_id,
                        Alert.status == AlertStatus.ACTIVE
                    )
                )
                active_alerts = result.scalars().all()
                
                if active_alerts:
                    # Desativar alertas
                    for alert in active_alerts:
                        alert.status = AlertStatus.INACTIVE
                
                # Soft delete
                product.status = OfferStatus.CANCELLED
                product.updated_at = datetime.utcnow()
                
                await session.commit()
                
                # Limpar cache
                cache_key = f"{self.cache_prefix}{product_id}"
                await redis_manager.delete_cache(cache_key)
                
                logger.info(f"Product deleted (soft): {product_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False
    
    async def get_categories(self) -> List[Category]:
        """Busca todas as categorias ativas"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Category)
                    .where(Category.is_active == True)
                    .order_by(Category.name)
                )
                categories = result.scalars().all()
                
                return list(categories)
                
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    async def create_category(self, name: str, emoji: str = None, description: str = None) -> Optional[Category]:
        """Cria nova categoria"""
        try:
            async with db_manager.get_session() as session:
                category = Category(
                    name=name,
                    emoji=emoji,
                    description=description,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(category)
                await session.commit()
                
                logger.info(f"Category created: {name}")
                return category
                
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            return None
    
    async def get_product_statistics(self, product_id: int) -> Dict[str, Any]:
        """Busca estatísticas de um produto"""
        try:
            async with db_manager.get_session_no_commit() as session:
                # Contar visualizações
                views_result = await session.execute(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.product_id == product_id)
                    .where(UserInteraction.interaction_type == 'view_product')
                )
                views_count = views_result.scalar() or 0
                
                # Contar cliques em comprar
                buy_result = await session.execute(
                    select(func.count(UserInteraction.id))
                    .where(UserInteraction.product_id == product_id)
                    .where(UserInteraction.interaction_type == 'click_buy')
                )
                buy_count = buy_result.scalar() or 0
                
                # Contar alertas ativos
                alerts_result = await session.execute(
                    select(func.count(Alert.id))
                    .where(Alert.product_id == product_id)
                    .where(Alert.status == AlertStatus.ACTIVE)
                )
                alerts_count = alerts_result.scalar() or 0
                
                return {
                    'product_id': product_id,
                    'views_count': views_count,
                    'buy_clicks': buy_count,
                    'active_alerts': alerts_count,
                    'conversion_rate': (buy_count / views_count * 100) if views_count > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting product statistics: {e}")
            return {}
    
    async def get_all_products(self, limit: int = 50, offset: int = 0) -> List[Product]:
        """Busca todos os produtos com paginação"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error getting all products: {e}")
            return []
    
    async def search_products(self, query: str, limit: int = 10) -> List[Product]:
        """Busca produtos por termo"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Product)
                    .where(or_(
                        Product.name.ilike(f"%{query}%"),
                        Product.description.ilike(f"%{query}%"),
                        Product.product_code.ilike(f"%{query}%")
                    ))
                    .limit(limit)
                )
                products = result.scalars().all()
                
                return list(products)
                
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
