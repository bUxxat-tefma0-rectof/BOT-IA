"""
Gerenciamento de Redis para cache e filas
"""
import redis.asyncio as redis
from typing import Optional, Any, Dict, List
import json
import pickle
from datetime import datetime, timedelta
from loguru import logger
from config import settings


class RedisManager:
    """Gerenciador de conexão com Redis"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        
    async def initialize(self):
        """Inicializa conexão com Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Testar conexão
            await self.redis_client.ping()
            logger.info("✅ Redis connection initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            # Redis não é crítico para o funcionamento básico
            self.redis_client = None
            logger.warning("⚠️ Continuing without Redis - cache disabled")
    
    async def close(self):
        """Fecha conexão com Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✅ Redis connection closed")
    
    # === Métodos de Cache ===
    
    async def set_cache(self, key: str, value: Any, expire_seconds: int = 3600):
        """Define valor no cache"""
        if not self.redis_client:
            return
        
        try:
            serialized = json.dumps(value) if not isinstance(value, (str, int, float)) else value
            await self.redis_client.setex(key, expire_seconds, serialized)
        except Exception as e:
            logger.error(f"Redis set_cache error: {e}")
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """Recupera valor do cache"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis get_cache error: {e}")
            return None
    
    async def delete_cache(self, key: str):
        """Remove valor do cache"""
        if not self.redis_client:
            return
        
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete_cache error: {e}")
    
    async def clear_cache_pattern(self, pattern: str):
        """Limpa cache por padrão"""
        if not self.redis_client:
            return
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear_cache_pattern error: {e}")
    
    # === Métodos de Fila ===
    
    async def enqueue(self, queue_name: str, data: Any):
        """Adiciona item à fila"""
        if not self.redis_client:
            return
        
        try:
            serialized = json.dumps(data)
            await self.redis_client.lpush(queue_name, serialized)
        except Exception as e:
            logger.error(f"Redis enqueue error: {e}")
    
    async def dequeue(self, queue_name: str) -> Optional[Any]:
        """Remove item da fila"""
        if not self.redis_client:
            return None
        
        try:
            data = await self.redis_client.rpop(queue_name)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis dequeue error: {e}")
            return None
    
    async def get_queue_length(self, queue_name: str) -> int:
        """Obtém tamanho da fila"""
        if not self.redis_client:
            return 0
        
        try:
            return await self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"Redis get_queue_length error: {e}")
            return 0
    
    # === Métodos de Sessão ===
    
    async def set_user_state(self, user_id: int, state: str, expire_seconds: int = 3600):
        """Define estado do usuário"""
        key = f"user_state:{user_id}"
        await self.set_cache(key, state, expire_seconds)
    
    async def get_user_state(self, user_id: int) -> Optional[str]:
        """Recupera estado do usuário"""
        key = f"user_state:{user_id}"
        return await self.get_cache(key)
    
    async def clear_user_state(self, user_id: int):
        """Limpa estado do usuário"""
        key = f"user_state:{user_id}"
        await self.delete_cache(key)
    
    # === Métodos de Rate Limiting ===
    
    async def check_rate_limit(self, user_id: int, action: str, limit: int = 10, window_seconds: int = 60) -> bool:
        """Verifica rate limit para ações"""
        if not self.redis_client:
            return True  # Se Redis não está disponível, permite a ação
        
        key = f"rate_limit:{user_id}:{action}"
        
        try:
            current = await self.redis_client.get(key)
            if current is None:
                await self.redis_client.setex(key, window_seconds, 1)
                return True
            
            if int(current) >= limit:
                return False
            
            await self.redis_client.incr(key)
            return True
        except Exception as e:
            logger.error(f"Redis check_rate_limit error: {e}")
            return True
    
    # === Métodos de Estatísticas ===
    
    async def increment_counter(self, counter_name: str, increment: int = 1):
        """Incrementa contador"""
        if not self.redis_client:
            return
        
        try:
            await self.redis_client.incrby(counter_name, increment)
        except Exception as e:
            logger.error(f"Redis increment_counter error: {e}")
    
    async def get_counter(self, counter_name: str) -> int:
        """Recupera contador"""
        if not self.redis_client:
            return 0
        
        try:
            value = await self.redis_client.get(counter_name)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Redis get_counter error: {e}")
            return 0
    
    # === Métodos de Lock ===
    
    async def acquire_lock(self, lock_name: str, expire_seconds: int = 30) -> bool:
        """Adquire lock para evitar execuções duplicadas"""
        if not self.redis_client:
            return True  # Se Redis não está disponível, permite a execução
        
        try:
            lock_key = f"lock:{lock_name}"
            return await self.redis_client.setnx(lock_key, "locked")
        except Exception as e:
            logger.error(f"Redis acquire_lock error: {e}")
            return True
    
    async def release_lock(self, lock_name: str):
        """Libera lock"""
        if not self.redis_client:
            return
        
        try:
            lock_key = f"lock:{lock_name}"
            await self.redis_client.delete(lock_key)
        except Exception as e:
            logger.error(f"Redis release_lock error: {e}")


# Instância global do gerenciador Redis
redis_manager = RedisManager()


async def init_redis():
    """Inicializa o Redis"""
    await redis_manager.initialize()
    logger.info("Redis initialization completed")
