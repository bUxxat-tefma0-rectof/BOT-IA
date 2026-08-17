"""
Teclados para usuários comuns
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional
from config import settings


def get_channel_verification_keyboard() -> InlineKeyboardMarkup:
    """Teclado para verificação de inscrição no canal"""
    keyboard = [
        [InlineKeyboardButton(
            text="📢 ENTRAR NO CANAL",
            url=f"https://t.me/{settings.CHANNEL_ID.replace('@', '')}"
        )],
        [InlineKeyboardButton(
            text="✅ VERIFICAR INSCRIÇÃO",
            callback_data="verify_membership"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Teclado principal do menu"""
    keyboard = [
        [InlineKeyboardButton(text="🔥 Ofertas Ativas", callback_data="show_offers")],
        [InlineKeyboardButton(text="📂 Categorias", callback_data="show_categories")],
        [InlineKeyboardButton(text="🔔 Meus Alertas", callback_data="my_alerts")],
        [
            InlineKeyboardButton(text="💬 Suporte", callback_data="support"),
            InlineKeyboardButton(text="ℹ️ Sobre", callback_data="about")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Teclado para visualização de produto"""
    keyboard = [
        [InlineKeyboardButton(
            text="🛒 COMPRAR AGORA",
            callback_data=f"buy_product_{product_id}"
        )],
        [InlineKeyboardButton(
            text="🔔 ATIVAR ALERTA",
            callback_data=f"activate_alert_{product_id}"
        )],
        [InlineKeyboardButton(
            text="⬅️ VOLTAR",
            callback_data="main_menu"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_offer_keyboard(product_id: int, has_alert: bool = False) -> InlineKeyboardMarkup:
    """Teclado para oferta de produto"""
    keyboard = [
        [InlineKeyboardButton(
            text="🛒 COMPRAR AGORA",
            callback_data=f"buy_product_{product_id}"
        )]
    ]
    
    if has_alert:
        keyboard.append([
            InlineKeyboardButton(
                text="🟢 ALERTA ATIVADO",
                callback_data=f"deactivate_alert_{product_id}"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="🔔 ATIVAR ALERTA",
                callback_data=f"activate_alert_{product_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ VOLTAR",
            callback_data="main_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_categories_keyboard(categories: Optional[List] = None) -> InlineKeyboardMarkup:
    """Teclado de categorias"""
    keyboard = []
    
    if categories:
        # Agrupar categorias em pares
        for i in range(0, len(categories), 2):
            row = []
            cat1 = categories[i]
            button1 = InlineKeyboardButton(
                text=f"{cat1.emoji or '📂'} {cat1.name}",
                callback_data=f"category_{cat1.id}"
            )
            row.append(button1)
            
            if i + 1 < len(categories):
                cat2 = categories[i + 1]
                button2 = InlineKeyboardButton(
                    text=f"{cat2.emoji or '📂'} {cat2.name}",
                    callback_data=f"category_{cat2.id}"
                )
                row.append(button2)
            
            keyboard.append(row)
    else:
        # Categorias padrão
        default_categories = [
            ("📱", "Celulares"),
            ("💻", "Computadores"),
            ("🎧", "Áudio"),
            ("🎮", "Games"),
            ("⌨️", "Periféricos"),
            ("🏠", "Casa Inteligente")
        ]
        
        for i in range(0, len(default_categories), 2):
            row = []
            emoji1, name1 = default_categories[i]
            row.append(InlineKeyboardButton(
                text=f"{emoji1} {name1}",
                callback_data=f"default_category_{i}"
            ))
            
            if i + 1 < len(default_categories):
                emoji2, name2 = default_categories[i + 1]
                row.append(InlineKeyboardButton(
                    text=f"{emoji2} {name2}",
                    callback_data=f"default_category_{i+1}"
                ))
            
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar ao Menu",
        callback_data="main_menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_alerts_keyboard() -> InlineKeyboardMarkup:
    """Teclado para gerenciamento de alertas"""
    keyboard = [
        [InlineKeyboardButton(text="🔔 Ver Alertas", callback_data="my_alerts")],
        [InlineKeyboardButton(text="🔥 Ver Ofertas", callback_data="show_offers")],
        [InlineKeyboardButton(text="⬅️ Menu Principal", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Teclado de confirmação"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Confirmar",
                callback_data=f"confirm_{action}"
            ),
            InlineKeyboardButton(
                text="❌ Cancelar",
                callback_data="cancel_action"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
