"""
Handlers do bot
"""
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.callback_handlers import router as callback_router

__all__ = ['user_router', 'admin_router', 'callback_router']
