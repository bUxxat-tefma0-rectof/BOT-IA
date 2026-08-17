"""
Validadores para dados do sistema
"""
from typing import Any, Dict, Optional, List
import re
from datetime import datetime
from urllib.parse import urlparse


def validate_product_data(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Valida dados de produto
    
    Args:
        data: Dicionário com dados do produto
    
    Returns:
        tuple: (é_válido, lista_de_erros)
    """
    errors = []
    
    # Validar nome
    if 'name' not in data or not data['name']:
        errors.append("Nome do produto é obrigatório")
    elif len(data['name']) < 3:
        errors.append("Nome do produto deve ter pelo menos 3 caracteres")
    
    # Validar preços
    if 'current_price' in data and data['current_price'] is not None:
        if not validate_price(data['current_price']):
            errors.append("Preço atual inválido")
    
    if 'original_price' in data and data['original_price'] is not None:
        if not validate_price(data['original_price']):
            errors.append("Preço original inválido")
    
    if 'target_price' in data and data['target_price'] is not None:
        if not validate_price(data['target_price']):
            errors.append("Preço alvo inválido")
    
    # Validar link
    if 'shopee_link' in data and data['shopee_link']:
        if not validate_url(data['shopee_link']):
            errors.append("Link da Shopee inválido")
    
    # Validar imagem
    if 'image_url' in data and data['image_url']:
        if not validate_url(data['image_url']):
            errors.append("URL da imagem inválida")
    
    # Validar datas
    if 'start_date' in data and data['start_date']:
        if not isinstance(data['start_date'], datetime):
            errors.append("Data de início inválida")
    
    if 'end_date' in data and data['end_date']:
        if not isinstance(data['end_date'], datetime):
            errors.append("Data de término inválida")
    
    # Validar categoria
    if 'category_id' in data and data['category_id'] is not None:
        if not isinstance(data['category_id'], int) or data['category_id'] <= 0:
            errors.append("Categoria inválida")
    
    return len(errors) == 0, errors


def validate_price(price: Any) -> bool:
    """
    Valida um preço
    
    Args:
        price: Preço a validar
    
    Returns:
        bool: True se válido
    """
    try:
        price_float = float(price)
        return price_float >= 0
    except:
        return False


def validate_url(url: str) -> bool:
    """
    Valida uma URL
    
    Args:
        url: URL a validar
    
    Returns:
        bool: True se válida
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def validate_category(category_data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Valida dados de categoria
    
    Args:
        category_data: Dicionário com dados da categoria
    
    Returns:
        tuple: (é_válido, lista_de_erros)
    """
    errors = []
    
    # Validar nome
    if 'name' not in category_data or not category_data['name']:
        errors.append("Nome da categoria é obrigatório")
    elif len(category_data['name']) < 2:
        errors.append("Nome da categoria deve ter pelo menos 2 caracteres")
    
    # Validar emoji
    if 'emoji' in category_data and category_data['emoji']:
        if len(category_data['emoji']) > 10:
            errors.append("Emoji muito longo")
    
    return len(errors) == 0, errors


def validate_schedule_data(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Valida dados de agendamento
    
    Args:
        data: Dicionário com dados do agendamento
    
    Returns:
        tuple: (é_válido, lista_de_erros)
    """
    errors = []
    
    # Validar nome
    if 'name' not in data or not data['name']:
        errors.append("Nome do agendamento é obrigatório")
    
    # Validar tipo
    valid_types = ['daily', 'weekly', 'custom']
    if 'schedule_type' in data:
        if data['schedule_type'] not in valid_types:
            errors.append(f"Tipo de agendamento deve ser um de: {', '.join(valid_types)}")
    
    # Validar dias da semana
    if 'days_of_week' in data and data['days_of_week']:
        for day in data['days_of_week']:
            if day < 0 or day > 6:
                errors.append("Dia da semana deve estar entre 0 (segunda) e 6 (domingo)")
    
    # Validar horários
    if 'times' in data and data['times']:
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        for time_str in data['times']:
            if not re.match(time_pattern, time_str):
                errors.append(f"Horário inválido: {time_str}. Use formato HH:MM")
    
    return len(errors) == 0, errors


def validate_template_data(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Valida dados de template
    
    Args:
        data: Dicionário com dados do template
    
    Returns:
        tuple: (é_válido, lista_de_erros)
    """
    errors = []
    
    # Validar nome
    if 'name' not in data or not data['name']:
        errors.append("Nome do template é obrigatório")
    
    # Validar texto
    if 'template_text' in data and data['template_text']:
        if len(data['template_text']) > 4000:
            errors.append("Texto do template muito longo (máximo 4000 caracteres)")
    
    return len(errors) == 0, errors


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """
    Sanitiza texto removendo caracteres problemáticos
    
    Args:
        text: Texto a sanitizar
        max_length: Tamanho máximo
    
    Returns:
        str: Texto sanitizado
    """
    if not text:
        return ""
    
    # Remover caracteres de controle
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    
    # Limitar tamanho
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def format_price(price: float) -> str:
    """
    Formata preço para exibição
    
    Args:
        price: Preço a formatar
    
    Returns:
        str: Preço formatado
    """
    return f"R$ {price:.2f}"


def format_discount(original: float, current: float) -> float:
    """
    Calcula percentual de desconto
    
    Args:
        original: Preço original
        current: Preço atual
    
    Returns:
        float: Percentual de desconto
    """
    if original <= 0:
        return 0
    
    discount = ((original - current) / original) * 100
    return max(0, discount)
