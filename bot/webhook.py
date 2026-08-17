"""
Webhook para manter o bot acordado no Render
Render free dorme após 15 minutos sem tráfego HTTP
"""
from aiohttp import web
import asyncio
from loguru import logger
import os

async def health_check(request):
    """Endpoint de health check"""
    return web.Response(
        text='OK',
        content_type='text/html',
        status=200
    )

async def start_webhook_server():
    """Inicia servidor webhook para health check"""
    try:
        app = web.Application()
        app.router.add_get('/health', health_check)
        app.router.add_get('/', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8000)))
        await site.start()
        
        logger.info(f"✅ Webhook server started on port {os.getenv('PORT', 8000)}")
        
        # Manter servidor rodando
        while True:
            await asyncio.sleep(3600)  # Dormir 1 hora
            
    except Exception as e:
        logger.error(f"❌ Error starting webhook server: {e}")
        raise

async def keep_alive():
    """Mantém o bot acordado fazendo auto-ping"""
    import aiohttp
    
    port = os.getenv('PORT', '8000')
    url = f"http://localhost:{port}/health"
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.debug("Health check OK")
                    else:
                        logger.warning(f"Health check failed: {response.status}")
        except Exception as e:
            logger.warning(f"Keep alive error: {e}")
        
        await asyncio.sleep(600)  # 10 minutos
