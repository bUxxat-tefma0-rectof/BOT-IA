"""
Teclados administrativos
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Menu principal administrativo"""
    keyboard = [
        [InlineKeyboardButton(text="📦 Produtos", callback_data="admin_products")],
        [InlineKeyboardButton(text="📢 Publicações", callback_data="admin_publications")],
        [InlineKeyboardButton(text="🔔 Alertas", callback_data="admin_alerts")],
        [InlineKeyboardButton(text="📊 Estatísticas", callback_data="admin_statistics")],
        [InlineKeyboardButton(text="📅 Agendamentos", callback_data="admin_schedules")],
        [InlineKeyboardButton(text="📝 Templates", callback_data="admin_templates")],
        [InlineKeyboardButton(text="📂 Categorias", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🔙 Sair", callback_data="exit_admin")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_management_menu() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de produtos"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Adicionar Produto", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="📋 Listar Produtos", callback_data="admin_list_products")],
        [InlineKeyboardButton(text="✏️ Editar Produto", callback_data="admin_edit_product")],
        [InlineKeyboardButton(text="🗑️ Excluir Produto", callback_data="admin_delete_product")],
        [InlineKeyboardButton(text="🔍 Pesquisar", callback_data="admin_search_product")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_publication_menu() -> InlineKeyboardMarkup:
    """Menu de publicações"""
    keyboard = [
        [InlineKeyboardButton(text="📢 Publicar Agora", callback_data="admin_publish_product")],
        [InlineKeyboardButton(text="📅 Agendar Publicação", callback_data="admin_schedule_publication")],
        [InlineKeyboardButton(text="📋 Publicações Ativas", callback_data="admin_active_publications")],
        [InlineKeyboardButton(text="🗑️ Excluir Publicação", callback_data="admin_delete_publication")],
        [InlineKeyboardButton(text="🔄 Republicar", callback_data="admin_republication")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_alerts_management_menu() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de alertas"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Produtos Monitorados", callback_data="admin_monitored_products")],
        [InlineKeyboardButton(text="👥 Usuários com Alertas", callback_data="admin_users_alerts")],
        [InlineKeyboardButton(text="⚙️ Configurar Condições", callback_data="admin_config_alerts")],
        [InlineKeyboardButton(text="🔄 Ativar/Desativar", callback_data="admin_toggle_monitoring")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_statistics_menu() -> InlineKeyboardMarkup:
    """Menu de estatísticas"""
    keyboard = [
        [InlineKeyboardButton(text="👥 Usuários", callback_data="admin_stats_users")],
        [InlineKeyboardButton(text="📦 Produtos", callback_data="admin_stats_products")],
        [InlineKeyboardButton(text="🔄 Interações", callback_data="admin_stats_interactions")],
        [InlineKeyboardButton(text="📈 Performance", callback_data="admin_stats_performance")],
        [InlineKeyboardButton(text="📊 Relatório Completo", callback_data="admin_full_report")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_menu() -> InlineKeyboardMarkup:
    """Menu de agendamentos"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Novo Agendamento", callback_data="admin_new_schedule")],
        [InlineKeyboardButton(text="📅 Ver Calendário", callback_data="admin_view_schedule")],
        [InlineKeyboardButton(text="✏️ Editar Agendamento", callback_data="admin_edit_schedule")],
        [InlineKeyboardButton(text="🗑️ Excluir Agendamento", callback_data="admin_delete_schedule")],
        [InlineKeyboardButton(text="🔄 Rotinas Automáticas", callback_data="admin_auto_routines")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_template_menu() -> InlineKeyboardMarkup:
    """Menu de templates"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Novo Template", callback_data="admin_new_template")],
        [InlineKeyboardButton(text="📋 Listar Templates", callback_data="admin_list_templates")],
        [InlineKeyboardButton(text="✏️ Editar Template", callback_data="admin_edit_template")],
        [InlineKeyboardButton(text="🗑️ Excluir Template", callback_data="admin_delete_template")],
        [InlineKeyboardButton(text="📝 Template de Oferta", callback_data="admin_offer_template")],
        [InlineKeyboardButton(text="⚡ Template Relâmpago", callback_data="admin_flash_template")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_menu() -> InlineKeyboardMarkup:
    """Menu de categorias"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Nova Categoria", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="📋 Listar Categorias", callback_data="admin_list_categories")],
        [InlineKeyboardButton(text="✏️ Editar Categoria", callback_data="admin_edit_category")],
        [InlineKeyboardButton(text="🗑️ Excluir Categoria", callback_data="admin_delete_category")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Teclado de confirmação para ações administrativas"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Confirmar",
                callback_data=f"admin_confirm_{action}"
            ),
            InlineKeyboardButton(
                text="❌ Cancelar",
                callback_data="admin_cancel"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_list_keyboard(products: List, action_prefix: str = "select") -> InlineKeyboardMarkup:
    """Teclado com lista de produtos"""
    keyboard = []
    
    for product in products[:10]:
        keyboard.append([InlineKeyboardButton(
            text=f"📦 {product.name} ({product.product_code})",
            callback_data=f"{action_prefix}_{product.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Voltar",
        callback_data="admin_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
