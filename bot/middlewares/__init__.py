"""
Middlewares do bot
"""
from bot.middlewares.auth_middleware import AuthMiddleware, AdminMiddleware
from bot.middlewares.channel_middleware import ChannelMembershipMiddleware

__all__ = [
    'AuthMiddleware',
    'AdminMiddleware',
    'ChannelMembershipMiddleware'
]
