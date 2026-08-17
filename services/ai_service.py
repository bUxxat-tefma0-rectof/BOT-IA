"""
Serviço de integração com IA
"""
from typing import Optional, Dict, Any, List
from loguru import logger
import json
import aiohttp

from config import settings


class AIService:
    """
    Serviço para integração com IA
    Auxilia na criação de conteúdo para produtos
    """
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4"
        self.max_tokens = 500
        self.temperature = 0.7
    
    async def generate_product_title(self, product_info: Dict[str, Any]) -> Optional[str]:
        """
        Gera título otimizado para o produto
        
        Args:
            product_info: Dicionário com informações do produto
        
        Returns:
            str: Título gerado ou None se erro
        """
        try:
            prompt = f"""
            Crie um título atraente para um produto tecnológico com as seguintes características:
            - Nome: {product_info.get('name', '')}
            - Categoria: {product_info.get('category', '')}
            - Preço: R$ {product_info.get('price', 0):.2f}
            - Desconto: {product_info.get('discount', 0):.0f}%
            
            O título deve:
            - Ser curto e impactante
            - Incluir emojis relevantes
            - Destacar o desconto se houver
            - Ser otimizado para Telegram
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating product title: {e}")
            return None
    
    async def generate_product_description(self, product_info: Dict[str, Any]) -> Optional[str]:
        """
        Gera descrição otimizada para o produto
        
        Args:
            product_info: Dicionário com informações do produto
        
        Returns:
            str: Descrição gerada ou None se erro
        """
        try:
            prompt = f"""
            Crie uma descrição persuasiva para um produto tecnológico:
            - Nome: {product_info.get('name', '')}
            - Características: {product_info.get('features', '')}
            - Preço original: R$ {product_info.get('original_price', 0):.2f}
            - Preço atual: R$ {product_info.get('current_price', 0):.2f}
            - Desconto: {product_info.get('discount', 0):.0f}%
            
            A descrição deve:
            - Destacar os benefícios
            - Enfatizar a economia
            - Criar senso de urgência
            - Ser concisa (máximo 200 caracteres)
            - Usar emojis moderadamente
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating product description: {e}")
            return None
    
    async def generate_promotional_text(self, product_info: Dict[str, Any]) -> Optional[str]:
        """
        Gera texto promocional para campanha
        
        Args:
            product_info: Dicionário com informações do produto
        
        Returns:
            str: Texto promocional ou None se erro
        """
        try:
            prompt = f"""
            Crie um texto promocional para oferta relâmpago:
            - Produto: {product_info.get('name', '')}
            - Preço: R$ {product_info.get('price', 0):.2f}
            - Desconto: {product_info.get('discount', 0):.0f}%
            - Tempo limitado: {product_info.get('time_limit', '24 horas')}
            
            O texto deve:
            - Criar urgência
            - Destacar a oferta
            - Incentivar ação imediata
            - Ser emocionante
            - Usar emojis de forma estratégica
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating promotional text: {e}")
            return None
    
    async def suggest_category(self, product_info: Dict[str, Any]) -> Optional[str]:
        """
        Sugere categoria para o produto
        
        Args:
            product_info: Dicionário com informações do produto
        
        Returns:
            str: Categoria sugerida ou None se erro
        """
        try:
            prompt = f"""
            Sugira uma categoria para o seguinte produto tecnológico:
            - Nome: {product_info.get('name', '')}
            - Descrição: {product_info.get('description', '')}
            
            Categorias disponíveis:
            📱 Celulares
            💻 Computadores
            🎧 Áudio
            🎮 Games
            ⌨️ Periféricos
            🏠 Casa inteligente
            🔌 Acessórios
            ⚡ Gadgets
            
            Responda apenas com o nome da categoria mais adequada.
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error suggesting category: {e}")
            return None
    
    async def generate_summary(self, text: str) -> Optional[str]:
        """
        Gera resumo de um texto
        
        Args:
            text: Texto para resumir
        
        Returns:
            str: Resumo gerado ou None se erro
        """
        try:
            prompt = f"""
            Crie um resumo conciso do seguinte texto:
            
            {text}
            
            O resumo deve:
            - Ter no máximo 50 palavras
            - Capturar os pontos principais
            - Ser claro e direto
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None
    
    async def highlight_discount(self, product_info: Dict[str, Any]) -> Optional[str]:
        """
        Cria destaque para desconto
        
        Args:
            product_info: Dicionário com informações do produto
        
        Returns:
            str: Texto de destaque ou None se erro
        """
        try:
            prompt = f"""
            Crie um destaque impactante para o desconto:
            - Produto: {product_info.get('name', '')}
            - Preço original: R$ {product_info.get('original_price', 0):.2f}
            - Preço atual: R$ {product_info.get('current_price', 0):.2f}
            - Desconto: {product_info.get('discount', 0):.0f}%
            - Economia: R$ {product_info.get('savings', 0):.2f}
            
            O destaque deve:
            - Enfatizar a economia
            - Usar números grandes e chamativos
            - Criar desejo de compra
            - Ser visualmente impactante
            """
            
            response = await self._call_ai_api(prompt)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error highlighting discount: {e}")
            return None
    
    async def _call_ai_api(self, prompt: str) -> Optional[str]:
        """
        Chama a API de IA
        
        Args:
            prompt: Prompt para enviar à IA
        
        Returns:
            str: Resposta da IA ou None se erro
        """
        try:
            if not self.api_key:
                logger.warning("OpenAI API key not configured")
                return None
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Você é um especialista em marketing digital e e-commerce."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        logger.error(f"AI API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling AI API: {e}")
            return None
