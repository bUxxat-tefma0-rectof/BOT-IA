"""
Handlers para estatísticas detalhadas
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from database.session import db_manager
from database.models import User, Product, Category, Alert, Publication, UserInteraction
from services.analytics_service import AnalyticsService
from bot.keyboards.admin_keyboards import get_admin_main_menu, get_statistics_menu
from config import settings

router = Router()
analytics_service = AnalyticsService()


@router.callback_query(F.data == "admin_stats_users")
async def user_statistics(callback: CallbackQuery):
    """Estatísticas de usuários"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    stats = await analytics_service.get_general_statistics()
    
    # Buscar dados adicionais
    async with db_manager.get_session_no_commit() as session:
        from sqlalchemy import select, func
        
        # Usuários ativos hoje
        today = datetime.utcnow().date()
        active_today = await session.scalar(
            select(func.count(User.id))
            .where(func.date(User.last_interaction) == today)
        )
        
        # Novos usuários hoje
        new_today = await session.scalar(
            select(func.count(User.id))
            .where(func.date(User.created_at) == today)
        )
    
    stats_text = (
        "👥 <b>ESTATÍSTICAS DE USUÁRIOS</b>\n\n"
        f"📊 <b>Total:</b> {stats.get('total_users', 0)}\n"
        f"✅ <b>Ativos:</b> {stats.get('active_users', 0)}\n"
        f"🕐 <b>Ativos hoje:</b> {active_today or 0}\n"
        f"🆕 <b>Novos hoje:</b> {new_today or 0}\n\n"
        f"📈 <b>Taxa de atividade:</b> "
        f"{(stats.get('active_users', 0) / stats.get('total_users', 1)) * 100:.1f}%"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Relatório Completo", callback_data="admin_full_report")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_statistics")]
    ]
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats_products")
async def product_statistics(callback: CallbackQuery):
    """Estatísticas de produtos"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    stats = await analytics_service.get_general_statistics()
    
    stats_text = (
        "📦 <b>ESTATÍSTICAS DE PRODUTOS</b>\n\n"
        f"📦 <b>Total:</b> {stats.get('total_products', 0)}\n"
        f"✅ <b>Ativos:</b> {stats.get('active_products', 0)}\n"
        f"📢 <b>Publicados:</b> {stats.get('published_products', 0)}\n\n"
        f"🏆 <b>Mais visto:</b> {stats.get('most_viewed_product', 'N/A')}\n"
        f"📂 <b>Categoria mais acessada:</b> {stats.get('most_accessed_category', 'N/A')}"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Relatório Completo", callback_data="admin_full_report")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_statistics")]
    ]
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats_interactions")
async def interaction_statistics(callback: CallbackQuery):
    """Estatísticas de interações"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    stats = await analytics_service.get_general_statistics()
    
    total_interactions = (stats.get('total_views', 0) + 
                         stats.get('buy_clicks', 0) + 
                         stats.get('alert_activations', 0))
    
    stats_text = (
        "🔄 <b>ESTATÍSTICAS DE INTERAÇÕES</b>\n\n"
        f"👁️ <b>Visualizações:</b> {stats.get('total_views', 0)}\n"
        f"🛒 <b>Cliques em comprar:</b> {stats.get('buy_clicks', 0)}\n"
        f"🔔 <b>Alertas ativados:</b> {stats.get('alert_activations', 0)}\n"
        f"📊 <b>Total de interações:</b> {total_interactions}\n\n"
        f"📈 <b>Taxa de conversão:</b> "
        f"{(stats.get('buy_clicks', 0) / stats.get('total_views', 1)) * 100:.2f}%"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Relatório Completo", callback_data="admin_full_report")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_statistics")]
    ]
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats_performance")
async def performance_statistics(callback: CallbackQuery):
    """Estatísticas de performance"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    # Buscar relatório dos últimos 7 dias
    report = await analytics_service.get_performance_report(days=7)
    
    stats_text = (
        "📈 <b>PERFORMANCE (ÚLTIMOS 7 DIAS)</b>\n\n"
    )
    
    if report.get('daily_interactions'):
        stats_text += "<b>Interações por dia:</b>\n"
        for day in report['daily_interactions'][-7:]:
            stats_text += f"• {day['date']}: {day['count']} interações\n"
    
    if report.get('top_products'):
        stats_text += "\n<b>Top produtos:</b>\n"
        for product in report['top_products'][:5]:
            stats_text += f"• {product['name']}: {product['interactions']} interações\n"
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Relatório Completo", callback_data="admin_full_report")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_statistics")]
    ]
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_full_report")
async def full_report(callback: CallbackQuery):
    """Relatório completo"""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Acesso negado!", show_alert=True)
        return
    
    stats = await analytics_service.get_general_statistics()
    report = await analytics_service.get_performance_report(days=30)
    
    report_text = (
        "📊 <b>RELATÓRIO COMPLETO</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>USUÁRIOS</b>\n"
        f"• Total: {stats.get('total_users', 0)}\n"
        f"• Ativos: {stats.get('active_users', 0)}\n\n"
        "📦 <b>PRODUTOS</b>\n"
        f"• Total: {stats.get('total_products', 0)}\n"
        f"• Ativos: {stats.get('active_products', 0)}\n"
        f"• Mais visto: {stats.get('most_viewed_product', 'N/A')}\n\n"
        "🔄 <b>INTERAÇÕES</b>\n"
        f"• Visualizações: {stats.get('total_views', 0)}\n"
        f"• Compras: {stats.get('buy_clicks', 0)}\n"
        f"• Alertas: {stats.get('alert_activations', 0)}\n"
        f"• Conversão: {(stats.get('buy_clicks', 0) / stats.get('total_views', 1)) * 100:.2f}%\n\n"
        "📂 <b>CATEGORIA MAIS ACESSADA</b>\n"
        f"• {stats.get('most_accessed_category', 'N/A')}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin_statistics")]
    ]
    
    await callback.message.edit_text(
        report_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()
