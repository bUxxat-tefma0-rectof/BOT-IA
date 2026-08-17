"""
Serviço de gerenciamento de agendamentos
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete
from loguru import logger

from database.session import db_manager
from database.models import Schedule, Product, Category
from redis_manager import redis_manager


class ScheduleService:
    """Serviço para gerenciamento de agendamentos"""
    
    def __init__(self):
        self.cache_prefix = "schedule:"
        self.cache_ttl = 3600
    
    async def create_schedule(self, schedule_data: Dict[str, Any]) -> Optional[Schedule]:
        """Cria novo agendamento"""
        try:
            async with db_manager.get_session() as session:
                schedule = Schedule(
                    name=schedule_data.get('name'),
                    schedule_type=schedule_data.get('schedule_type', 'daily'),
                    days_of_week=schedule_data.get('days_of_week'),
                    times=schedule_data.get('times', []),
                    product_id=schedule_data.get('product_id'),
                    category_id=schedule_data.get('category_id'),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(schedule)
                await session.commit()
                
                logger.info(f"Schedule created: {schedule.name}")
                return schedule
                
        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return None
    
    async def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        """Busca agendamento por ID"""
        try:
            async with db_manager.get_session_no_commit() as session:
                schedule = await session.get(Schedule, schedule_id)
                return schedule
                
        except Exception as e:
            logger.error(f"Error getting schedule: {e}")
            return None
    
    async def get_all_schedules(self) -> List[Schedule]:
        """Busca todos os agendamentos"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Schedule)
                    .order_by(Schedule.created_at.desc())
                )
                schedules = result.scalars().all()
                
                return list(schedules)
                
        except Exception as e:
            logger.error(f"Error getting all schedules: {e}")
            return []
    
    async def get_active_schedules(self) -> List[Schedule]:
        """Busca agendamentos ativos"""
        try:
            async with db_manager.get_session_no_commit() as session:
                result = await session.execute(
                    select(Schedule)
                    .where(Schedule.is_active == True)
                    .order_by(Schedule.name)
                )
                schedules = result.scalars().all()
                
                return list(schedules)
                
        except Exception as e:
            logger.error(f"Error getting active schedules: {e}")
            return []
    
    async def update_schedule(self, schedule_id: int, update_data: Dict[str, Any]) -> bool:
        """Atualiza agendamento"""
        try:
            async with db_manager.get_session() as session:
                schedule = await session.get(Schedule, schedule_id)
                
                if not schedule:
                    return False
                
                for key, value in update_data.items():
                    if hasattr(schedule, key):
                        setattr(schedule, key, value)
                
                schedule.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Schedule updated: {schedule_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating schedule: {e}")
            return False
    
    async def delete_schedule(self, schedule_id: int) -> bool:
        """Exclui agendamento"""
        try:
            async with db_manager.get_session() as session:
                schedule = await session.get(Schedule, schedule_id)
                
                if not schedule:
                    return False
                
                await session.delete(schedule)
                await session.commit()
                
                logger.info(f"Schedule deleted: {schedule_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting schedule: {e}")
            return False
    
    async def toggle_schedule(self, schedule_id: int) -> bool:
        """Ativa/desativa agendamento"""
        try:
            async with db_manager.get_session() as session:
                schedule = await session.get(Schedule, schedule_id)
                
                if not schedule:
                    return False
                
                schedule.is_active = not schedule.is_active
                schedule.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Schedule toggled: {schedule_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error toggling schedule: {e}")
            return False
    
    async def get_schedules_for_time(self, current_time: datetime) -> List[Schedule]:
        """
        Busca agendamentos que devem executar em um horário específico
        
        Args:
            current_time: Horário atual
        
        Returns:
            List: Agendamentos para executar
        """
        try:
            schedules = await self.get_active_schedules()
            
            matching_schedules = []
            
            for schedule in schedules:
                if await self.should_run_now(schedule, current_time):
                    matching_schedules.append(schedule)
            
            return matching_schedules
            
        except Exception as e:
            logger.error(f"Error getting schedules for time: {e}")
            return []
    
    async def should_run_now(self, schedule: Schedule, current_time: datetime) -> bool:
        """
        Verifica se agendamento deve executar agora
        
        Args:
            schedule: Agendamento a verificar
            current_time: Horário atual
        
        Returns:
            bool: True se deve executar
        """
        try:
            # Verificar dias da semana
            if schedule.days_of_week:
                current_day = current_time.weekday()
                if current_day not in schedule.days_of_week:
                    return False
            
            # Verificar horários
            if schedule.times:
                current_hour = current_time.hour
                current_minute = current_time.minute
                
                for time_str in schedule.times:
                    try:
                        target_hour, target_minute = map(int, time_str.split(':'))
                        
                        if current_hour == target_hour and current_minute == target_minute:
                            # Verificar se já executou nesta hora
                            cache_key = f"{self.cache_prefix}executed:{schedule.id}:{time_str}"
                            executed = await redis_manager.get_cache(cache_key)
                            
                            if not executed:
                                # Marcar como executado
                                await redis_manager.set_cache(cache_key, True, 3600)
                                return True
                    
                    except:
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking schedule execution: {e}")
            return False
    
    async def get_schedule_statistics(self) -> Dict[str, Any]:
        """Busca estatísticas de agendamentos"""
        try:
            async with db_manager.get_session_no_commit() as session:
                from sqlalchemy import select, func
                
                total = await session.scalar(
                    select(func.count(Schedule.id))
                )
                
                active = await session.scalar(
                    select(func.count(Schedule.id))
                    .where(Schedule.is_active == True)
                )
                
                daily = await session.scalar(
                    select(func.count(Schedule.id))
                    .where(Schedule.schedule_type == 'daily')
                )
                
                weekly = await session.scalar(
                    select(func.count(Schedule.id))
                    .where(Schedule.schedule_type == 'weekly')
                )
                
                return {
                    'total_schedules': total or 0,
                    'active_schedules': active or 0,
                    'daily_schedules': daily or 0,
                    'weekly_schedules': weekly or 0
                }
                
        except Exception as e:
            logger.error(f"Error getting schedule statistics: {e}")
            return {}
