"""
Serviço de gerenciamento de templates
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete
from loguru import logger

from database.session import db_manager
from database.models import Template, Product, Publication
from redis_manager import redis_manager


class TemplateService:
    """Serviço para gerenciamento de templates"""
    
    def __init__(self):
        self.cache_prefix = "template:"
        self.cache_ttl = 3600
    
    async def create_template(self, template_data: Dict[str, Any]) -> Optional[Template]:
        """Cria novo template"""
        try:
            async with db_manager.get_session() as session:
                template = Template(
                    name=template_data.get('name'),
                    description=template_data.get('description'),
                    template_text=template_data.get('template_text'),
                    template_buttons=template_data.get('template_buttons', []),
                    template_image=template_data.get('template_image'),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(template)
                await session.commit()
                
                logger.info(f"Template created: {template.name}")
                return template
                
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            return None
    
    async def get_template(self, template_id: int) -> Optional[Template]:
        """Busca template por ID"""
        try:
            async with db_manager.get_session_no_commit() as session:
                template = await session.get(Template, template_id)
                return template
                
        except Exception as e:
            logger.error(f"Error getting template: {e}")
            return None
    
    async def get_all_templates(self) -> List[Template]:
        """Busca todos os templates"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Template)
                    .order_by(Template.created_at.desc())
                )
                templates = result.scalars().all()
                
                return list(templates)
                
        except Exception as e:
            logger.error(f"Error getting all templates: {e}")
            return []
    
    async def get_active_templates(self) -> List[Template]:
        """Busca templates ativos"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Template)
                    .where(Template.is_active == True)
                    .order_by(Template.name)
                )
                templates = result.scalars().all()
                
                return list(templates)
                
        except Exception as e:
            logger.error(f"Error getting active templates: {e}")
            return []
    
    async def update_template(self, template_id: int, update_data: Dict[str, Any]) -> bool:
        """Atualiza template"""
        try:
            async with db_manager.get_session() as session:
                template = await session.get(Template, template_id)
                
                if not template:
                    return False
                
                for key, value in update_data.items():
                    if hasattr(template, key):
                        setattr(template, key, value)
                
                template.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Template updated: {template_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating template: {e}")
            return False
    
    async def delete_template(self, template_id: int) -> bool:
        """Exclui template"""
        try:
            async with db_manager.get_session() as session:
                template = await session.get(Template, template_id)
                
                if not template:
                    return False
                
                await session.delete(template)
                await session.commit()
                
                logger.info(f"Template deleted: {template_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting template: {e}")
            return False
    
    async def apply_template(self, template_id: int, product: Product) -> str:
        """
        Aplica template a um produto
        
        Args:
            template_id: ID do template
            product: Produto para formatar
        
        Returns:
            str: Texto formatado
        """
        try:
            template = await self.get_template(template_id)
            
            if not template or not template.template_text:
                return ""
            
            # Substituir variáveis
            text = template.template_text
            
            replacements = {
                '{product_name}': product.name,
                '{original_price}': f"{product.original_price:.2f}" if product.original_price else "N/A",
                '{current_price}': f"{product.current_price:.2f}" if product.current_price else "N/A",
                '{discount}': f"{product.discount_percentage:.0f}" if product.discount_percentage else "0",
                '{description}': product.description or "Sem descrição",
                '{product_code}': product.product_code,
                '{shopee_link}': product.shopee_link or "#"
            }
            
            for key, value in replacements.items():
                text = text.replace(key, value)
            
            return text
            
        except Exception as e:
            logger.error(f"Error applying template: {e}")
            return ""
