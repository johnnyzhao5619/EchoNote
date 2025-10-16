"""
API 使用量跟踪器

跟踪云服务语音识别 API 的使用量和费用
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

logger = logging.getLogger(__name__)


class UsageTracker:
    """API 使用量跟踪器"""

    # API 定价（每分钟，单位：美元）
    PRICING = {
        'openai': Decimal('0.006'),      # $0.006 per minute
        'google': Decimal('0.006'),      # $0.006 per minute (前 60 分钟免费)
        'azure': Decimal('0.001'),       # $1 per hour = $0.0167 per minute (标准版)
    }

    def __init__(self, db_connection):
        """
        初始化使用量跟踪器
        
        Args:
            db_connection: 数据库连接对象
        """
        self.db = db_connection
        logger.info("Usage tracker initialized")

    def record_usage(self, engine: str, duration_seconds: float, 
                    timestamp: Optional[datetime] = None) -> str:
        """
        记录 API 使用量
        
        Args:
            engine: 引擎名称 ('openai', 'google', 'azure')
            duration_seconds: 音频时长（秒）
            timestamp: 使用时间戳（可选，默认为当前时间）
            
        Returns:
            str: 使用记录 ID
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # 计算费用
        duration_minutes = Decimal(duration_seconds) / Decimal(60)
        cost = self._calculate_cost_internal(engine, duration_minutes)
        
        # 生成记录 ID
        record_id = str(uuid.uuid4())
        
        # 保存到数据库
        try:
            with self.db.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO api_usage (id, engine, duration_seconds, cost, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (record_id, engine, duration_seconds, float(cost), timestamp))
            
            logger.info(f"Recorded usage: engine={engine}, duration={duration_seconds}s, cost=${cost}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to record usage: {e}")
            raise

    def calculate_cost(self, engine: str, duration_seconds: float) -> float:
        """
        计算使用费用（公开方法）
        
        Args:
            engine: 引擎名称
            duration_seconds: 音频时长（秒）
            
        Returns:
            float: 费用（美元）
        """
        duration_minutes = Decimal(duration_seconds) / Decimal(60)
        cost = self._calculate_cost_internal(engine, duration_minutes)
        return float(cost)

    def _calculate_cost_internal(self, engine: str, duration_minutes: Decimal) -> Decimal:
        """
        内部费用计算方法
        
        Args:
            engine: 引擎名称
            duration_minutes: 时长（分钟）
            
        Returns:
            Decimal: 费用（美元）
        """
        if engine not in self.PRICING:
            logger.warning(f"Unknown engine: {engine}, using default pricing")
            return Decimal('0.006') * duration_minutes
        
        price_per_minute = self.PRICING[engine]
        cost = price_per_minute * duration_minutes
        
        return cost.quantize(Decimal('0.0001'))  # 保留 4 位小数

    def get_monthly_usage(self, engine: Optional[str] = None, 
                         year: Optional[int] = None, 
                         month: Optional[int] = None) -> Dict:
        """
        获取月度使用统计
        
        Args:
            engine: 引擎名称（可选，None 表示所有引擎）
            year: 年份（可选，默认为当前年份）
            month: 月份（可选，默认为当前月份）
            
        Returns:
            Dict: 使用统计
            {
                "engine": str,
                "total_duration_seconds": float,
                "total_duration_minutes": float,
                "total_cost": float,
                "usage_count": int,
                "period": {
                    "year": int,
                    "month": int
                }
            }
        """
        now = datetime.now()
        year = year or now.year
        month = month or now.month
        
        # 计算月份的开始和结束时间
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        try:
            with self.db.get_cursor() as cursor:
                # 构建查询
                if engine:
                    query = """
                        SELECT 
                            engine,
                            SUM(duration_seconds) as total_duration,
                            SUM(cost) as total_cost,
                            COUNT(*) as usage_count
                        FROM api_usage
                        WHERE engine = ? AND timestamp >= ? AND timestamp < ?
                        GROUP BY engine
                    """
                    cursor.execute(query, (engine, start_date, end_date))
                else:
                    query = """
                        SELECT 
                            engine,
                            SUM(duration_seconds) as total_duration,
                            SUM(cost) as total_cost,
                            COUNT(*) as usage_count
                        FROM api_usage
                        WHERE timestamp >= ? AND timestamp < ?
                        GROUP BY engine
                    """
                    cursor.execute(query, (start_date, end_date))
                
                results = cursor.fetchall()
            
                # 如果查询单个引擎
                if engine:
                    if results:
                        row = results[0]
                        return {
                            "engine": row[0],
                            "total_duration_seconds": row[1] or 0.0,
                            "total_duration_minutes": (row[1] or 0.0) / 60,
                            "total_cost": row[2] or 0.0,
                            "usage_count": row[3] or 0,
                            "period": {
                                "year": year,
                                "month": month
                            }
                        }
                    else:
                        return {
                            "engine": engine,
                            "total_duration_seconds": 0.0,
                            "total_duration_minutes": 0.0,
                            "total_cost": 0.0,
                            "usage_count": 0,
                            "period": {
                                "year": year,
                                "month": month
                            }
                        }
                else:
                    # 返回所有引擎的统计
                    stats = {}
                    total_duration = 0.0
                    total_cost = 0.0
                    total_count = 0
                    
                    for row in results:
                        engine_name = row[0]
                        duration = row[1] or 0.0
                        cost = row[2] or 0.0
                        count = row[3] or 0
                        
                        stats[engine_name] = {
                            "total_duration_seconds": duration,
                            "total_duration_minutes": duration / 60,
                            "total_cost": cost,
                            "usage_count": count
                        }
                        
                        total_duration += duration
                        total_cost += cost
                        total_count += count
                    
                    return {
                        "engines": stats,
                        "total_duration_seconds": total_duration,
                        "total_duration_minutes": total_duration / 60,
                        "total_cost": total_cost,
                        "total_usage_count": total_count,
                        "period": {
                            "year": year,
                            "month": month
                        }
                    }
                
        except Exception as e:
            logger.error(f"Failed to get monthly usage: {e}")
            raise

    def get_usage_history(self, engine: Optional[str] = None, 
                         days: int = 30, 
                         limit: int = 100) -> list:
        """
        获取使用历史记录
        
        Args:
            engine: 引擎名称（可选）
            days: 查询最近多少天的记录
            limit: 最大返回记录数
            
        Returns:
            list: 使用记录列表
        """
        start_date = datetime.now() - timedelta(days=days)
        
        try:
            with self.db.get_cursor() as cursor:
                if engine:
                    query = """
                        SELECT id, engine, duration_seconds, cost, timestamp
                        FROM api_usage
                        WHERE engine = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """
                    cursor.execute(query, (engine, start_date, limit))
                else:
                    query = """
                        SELECT id, engine, duration_seconds, cost, timestamp
                        FROM api_usage
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """
                    cursor.execute(query, (start_date, limit))
                
                results = cursor.fetchall()
                
                # 转换为字典列表
                history = []
                for row in results:
                    history.append({
                        "id": row[0],
                        "engine": row[1],
                        "duration_seconds": row[2],
                        "duration_minutes": row[2] / 60,
                        "cost": row[3],
                        "timestamp": row[4]
                    })
                
                return history
            
        except Exception as e:
            logger.error(f"Failed to get usage history: {e}")
            raise

    def estimate_cost(self, engine: str, duration_seconds: float) -> float:
        """
        估算使用费用

        Args:
            engine: 引擎名称
            duration_seconds: 音频时长（秒）

        Returns:
            float: 预估费用（美元）
        """
        duration_minutes = Decimal(duration_seconds) / Decimal(60)
        cost = self._calculate_cost_internal(engine, duration_minutes)
        return float(cost)
