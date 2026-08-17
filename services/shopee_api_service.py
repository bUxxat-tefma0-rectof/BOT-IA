"""
Serviço de integração com a API da Shopee
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
import aiohttp
import hashlib
import hmac
import time
import json

from config import settings
from redis_manager import redis_manager


class ShopeeAPIService:
    """
    Serviço para integração com a API oficial da Shopee
    Documentação: https://open.shopee.com/
    """
    
    def __init__(self):
        self.api_key = settings.SHOPEE_API_KEY
        self.api_url = "https://partner.shopeemobile.com/api/v2"
        self.partner_id = None
        self.shop_id = None
        self.cache_prefix = "shopee:"
        self.cache_ttl = 300  # 5 minutos
        
    async def initialize(self):
        """Inicializa credenciais da API"""
        # TODO: Configurar partner_id e shop_id
        # Estes valores devem ser obtidos no painel do parceiro Shopee
        self.partner_id = getattr(settings, 'SHOPEE_PARTNER_ID', None)
        self.shop_id = getattr(settings, 'SHOPEE_SHOP_ID', None)
        
        if not self.api_key:
            logger.warning("Shopee API key not configured")
            return False
        
        return True
    
    async def get_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca informações de um produto
        
        Args:
            product_id: ID do produto na Shopee
        
        Returns:
            Dict: Informações do produto
        """
        try:
            # Verificar cache
            cache_key = f"{self.cache_prefix}product:{product_id}"
            cached = await redis_manager.get_cache(cache_key)
            
            if cached:
                return cached
            
            # Buscar da API
            endpoint = "/product/get_item_base_info"
            params = {
                "item_id_list": [int(product_id)]
            }
            
            response = await self._make_request(endpoint, params)
            
            if response:
                # Cachear resultado
                await redis_manager.set_cache(cache_key, response, self.cache_ttl)
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product info: {e}")
            return None
    
    async def get_product_price(self, product_id: str) -> Optional[float]:
        """
        Busca preço atual de um produto
        
        Args:
            product_id: ID do produto na Shopee
        
        Returns:
            float: Preço atual
        """
        try:
            product_info = await self.get_product_info(product_id)
            
            if product_info and 'price' in product_info:
                return float(product_info['price'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product price: {e}")
            return None
    
    async def get_product_stock(self, product_id: str) -> Optional[int]:
        """
        Busca estoque de um produto
        
        Args:
            product_id: ID do produto na Shopee
        
        Returns:
            int: Quantidade em estoque
        """
        try:
            product_info = await self.get_product_info(product_id)
            
            if product_info and 'stock' in product_info:
                return int(product_info['stock'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product stock: {e}")
            return None
    
    async def get_product_discount(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca informações de desconto de um produto
        
        Args:
            product_id: ID do produto na Shopee
        
        Returns:
            Dict: Informações de desconto
        """
        try:
            endpoint = "/product/get_item_discount"
            params = {
                "item_id": int(product_id)
            }
            
            response = await self._make_request(endpoint, params)
            
            if response:
                return {
                    'original_price': response.get('original_price'),
                    'discounted_price': response.get('discounted_price'),
                    'discount_percentage': response.get('discount_percentage'),
                    'discount_type': response.get('discount_type')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product discount: {e}")
            return None
    
    async def get_product_by_link(self, shopee_link: str) -> Optional[Dict[str, Any]]:
        """
        Extrai ID do produto de um link da Shopee e busca informações
        
        Args:
            shopee_link: Link do produto na Shopee
        
        Returns:
            Dict: Informações do produto
        """
        try:
            # Extrair ID do produto do link
            product_id = await self.extract_product_id(shopee_link)
            
            if not product_id:
                logger.warning(f"Could not extract product ID from link: {shopee_link}")
                return None
            
            return await self.get_product_info(product_id)
            
        except Exception as e:
            logger.error(f"Error getting product by link: {e}")
            return None
    
    async def extract_product_id(self, shopee_link: str) -> Optional[str]:
        """
        Extrai ID do produto de um link da Shopee
        
        Args:
            shopee_link: Link do produto
        
        Returns:
            str: ID do produto
        """
        try:
            # Padrões comuns de link da Shopee
            import re
            
            # Padrão: i.{ID}.{market}
            pattern1 = r'i\.(\d+)\.'
            match = re.search(pattern1, shopee_link)
            if match:
                return match.group(1)
            
            # Padrão: ?item_id={ID}
            pattern2 = r'[?&]item_id=(\d+)'
            match = re.search(pattern2, shopee_link)
            if match:
                return match.group(1)
            
            # Padrão: /product/{shop_id}/{item_id}
            pattern3 = r'/product/\d+/(\d+)'
            match = re.search(pattern3, shopee_link)
            if match:
                return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting product ID: {e}")
            return None
    
    async def search_products(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca produtos na Shopee
        
        Args:
            keyword: Termo de busca
            limit: Número máximo de resultados
        
        Returns:
            List: Lista de produtos
        """
        try:
            endpoint = "/product/search"
            params = {
                "keyword": keyword,
                "limit": limit
            }
            
            response = await self._make_request(endpoint, params)
            
            if response and 'items' in response:
                return response['items']
            
            return []
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    async def monitor_price(self, product_id: str, callback_url: str = None) -> bool:
        """
        Configura monitoramento de preço para um produto
        
        Args:
            product_id: ID do produto
            callback_url: URL para receber notificações
        
        Returns:
            bool: True se configurado
        """
        try:
            endpoint = "/product/create_price_monitor"
            params = {
                "item_id": int(product_id),
                "callback_url": callback_url
            }
            
            response = await self._make_request(endpoint, params)
            
            return response is not None
            
        except Exception as e:
            logger.error(f"Error setting up price monitoring: {e}")
            return False
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Faz requisição à API da Shopee
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros da requisição
        
        Returns:
            Dict: Resposta da API
        """
        try:
            if not self.api_key:
                logger.warning("Shopee API key not configured")
                return None
            
            # Gerar timestamp
            timestamp = int(time.time())
            
            # Preparar payload
            payload = {
                **params,
                "partner_id": self.partner_id,
                "shop_id": self.shop_id,
                "timestamp": timestamp
            }
            
            # Gerar assinatura
            signature = self._generate_signature(payload)
            
            # Headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # URL completa
            url = f"{self.api_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        logger.error(f"Shopee API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error making request to Shopee API: {e}")
            return None
    
    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """
        Gera assinatura para autenticação
        
        Args:
            payload: Dados para assinar
        
        Returns:
            str: Assinatura gerada
        """
        try:
            # Ordenar payload
            sorted_payload = json.dumps(payload, sort_keys=True)
            
            # Gerar HMAC
            signature = hmac.new(
                self.api_key.encode('utf-8'),
                sorted_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            return ""
