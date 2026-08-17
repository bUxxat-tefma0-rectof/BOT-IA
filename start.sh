#!/bin/bash

# Script de inicialização do bot no Render

echo "🚀 Iniciando Tech Offers Bot..."

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python não encontrado!"
    exit 1
fi

# Inicializar banco de dados
echo "📦 Inicializando banco de dados..."
python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')

async def init():
    from database.session import db_manager, init_database
    from services.button_config_service import ButtonConfigService
    from database.models import Category, Template
    from datetime import datetime
    
    try:
        await init_database()
        
        # Criar dados padrão se não existirem
        async with db_manager.get_session() as session:
            from sqlalchemy import select
            
            # Verificar categorias
            result = await session.execute(select(Category))
            categories = result.scalars().all()
            
            if not categories:
                # Criar categorias padrão
                default_categories = [
                    {'name': 'Celulares', 'emoji': '📱'},
                    {'name': 'Computadores', 'emoji': '💻'},
                    {'name': 'Áudio', 'emoji': '🎧'},
                    {'name': 'Games', 'emoji': '🎮'},
                    {'name': 'Periféricos', 'emoji': '⌨️'},
                    {'name': 'Casa Inteligente', 'emoji': '🏠'},
                    {'name': 'Acessórios', 'emoji': '🔌'},
                    {'name': 'Gadgets', 'emoji': '⚡'}
                ]
                
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
                print('✅ Categorias padrão criadas')
            
            # Verificar templates
            result = await session.execute(select(Template))
            templates = result.scalars().all()
            
            if not templates:
                # Criar templates padrão
                default_templates = [
                    {
                        'name': 'Template de Oferta Padrão',
                        'description': 'Template para ofertas regulares',
                        'template_text': '''🔥 OFERTA TECNOLÓGICA

📦 {product_name}

💰 De: R$ {original_price}
🔥 Por: R$ {current_price}
📊 Desconto: {discount}%

📝 {description}

🆔 Código: {product_code}'''
                    },
                    {
                        'name': 'Template de Oferta Relâmpago',
                        'description': 'Template para ofertas relâmpago',
                        'template_text': '''🚨 OFERTA RELÂMPAGO ⚡

📦 {product_name}

💥 De R$ {original_price}
⚡ Por apenas R$ {current_price}

🔥 {discount}% DE DESCONTO!

⏰ TEMPO LIMITADO!'''
                    }
                ]
                
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
                print('✅ Templates padrão criados')
        
        print('✅ Banco de dados inicializado com sucesso!')
        
    except Exception as e:
        print(f'❌ Erro ao inicializar banco: {e}')
        raise
    
    finally:
        await db_manager.close()

asyncio.run(init())
"

# Iniciar bot
echo "🤖 Iniciando bot..."
python3 -m bot.main
