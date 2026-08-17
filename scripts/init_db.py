"""
Script para inicializar o banco de dados
"""
import asyncio
import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_manager, init_database
from database.models import Base
from services.button_config_service import ButtonConfigService
from loguru import logger


async def initialize_database():
    """Inicializa o banco de dados com dados padrão"""
    try:
        logger.info("Starting database initialization...")
        
        # Inicializar conexão
        await db_manager.initialize()
        
        # Criar tabelas
        await db_manager.create_tables()
        logger.info("✅ Tables created")
        
        # Criar dados padrão
        await create_default_data()
        
        logger.info("✅ Database initialization completed")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    finally:
        await db_manager.close()


async def create_default_data():
    """Cria dados padrão no banco"""
    try:
        # Criar botões padrão
        button_service = ButtonConfigService()
        await button_service.create_default_buttons()
        logger.info("✅ Default buttons created")
        
        # Criar categorias padrão
        from database.models import Category
        from datetime import datetime
        
        default_categories = [
            {"name": "Celulares", "emoji": "📱"},
            {"name": "Computadores", "emoji": "💻"},
            {"name": "Áudio", "emoji": "🎧"},
            {"name": "Games", "emoji": "🎮"},
            {"name": "Periféricos", "emoji": "⌨️"},
            {"name": "Casa Inteligente", "emoji": "🏠"},
            {"name": "Acessórios", "emoji": "🔌"},
            {"name": "Gadgets", "emoji": "⚡"}
        ]
        
        async with db_manager.get_session() as session:
            for cat_data in default_categories:
                category = Category(
                    name=cat_data['name'],
                    emoji=cat_data['emoji'],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(category)
            
            await session.commit()
            logger.info(f"✅ {len(default_categories)} default categories created")
        
        # Criar templates padrão
        from database.models import Template
        
        default_templates = [
            {
                'name': 'Template de Oferta Padrão',
                'description': 'Template para ofertas regulares',
                'template_text': """🔥 OFERTA TECNOLÓGICA

📦 {product_name}

💰 De: R$ {original_price}
🔥 Por: R$ {current_price}
📊 Desconto: {discount}%

📝 {description}

🆔 Código: {product_code}"""
            },
            {
                'name': 'Template de Oferta Relâmpago',
                'description': 'Template para ofertas relâmpago',
                'template_text': """🚨 OFERTA RELÂMPAGO ⚡

📦 {product_name}

💥 De R$ {original_price}
⚡ Por apenas R$ {current_price}

🔥 {discount}% DE DESCONTO!

⏰ TEMPO LIMITADO!"""
            }
        ]
        
        async with db_manager.get_session() as session:
            for template_data in default_templates:
                template = Template(
                    name=template_data['name'],
                    description=template_data['description'],
                    template_text=template_data['template_text'],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(template)
            
            await session.commit()
            logger.info(f"✅ {len(default_templates)} default templates created")
        
    except Exception as e:
        logger.error(f"Error creating default data: {e}")
        raise


async def reset_database():
    """Reseta o banco de dados"""
    try:
        logger.warning("Resetting database...")
        
        await db_manager.initialize()
        await db_manager.drop_tables()
        await db_manager.create_tables()
        
        await create_default_data()
        
        logger.info("✅ Database reset completed")
        
    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_database())
    else:
        asyncio.run(initialize_database())
