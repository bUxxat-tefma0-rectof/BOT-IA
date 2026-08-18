"""
Handlers do bot - Todos registrados
"""
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.callback_handlers import router as callback_router
from bot.handlers.promotion_handlers import router as promotion_router
from bot.handlers.button_handlers import router as button_router
from bot.handlers.deeplink_handlers import router as deeplink_router

__all__ = [
    'user_router',
    'admin_router',
    'callback_router',
    'promotion_router',
    'button_router',
    'deeplink_router'
]
