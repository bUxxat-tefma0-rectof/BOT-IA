"""
Teclados do bot
"""
from bot.keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_product_keyboard,
    get_categories_keyboard,
    get_alerts_keyboard,
    get_channel_verification_keyboard,
    get_product_offer_keyboard
)

from bot.keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_product_management_menu,
    get_publication_menu,
    get_alerts_management_menu,
    get_statistics_menu,
    get_schedule_menu,
    get_template_menu,
    get_category_menu,
    get_confirmation_keyboard
)

__all__ = [
    'get_main_menu_keyboard',
    'get_product_keyboard',
    'get_categories_keyboard',
    'get_alerts_keyboard',
    'get_channel_verification_keyboard',
    'get_product_offer_keyboard',
    'get_admin_main_menu',
    'get_product_management_menu',
    'get_publication_menu',
    'get_alerts_management_menu',
    'get_statistics_menu',
    'get_schedule_menu',
    'get_template_menu',
    'get_category_menu',
    'get_confirmation_keyboard'
]
