"""
通用数据库工具（同步版本）

此模块提供基于 SQLAlchemy 2.x 同步引擎的数据库访问封装，支持 MySQL 与 PostgreSQL。
使用同步驱动以避免 Celery + gevent 环境下的 asyncio 事件循环冲突。
"""

from __future__ import annotations
from urllib.parse import quote_plus
import os
from typing import Any, Dict, Iterable, List, Optional, Union

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from InsightEngine.utils.config import settings

__all__ = [
    "get_engine",
    "fetch_all",
]


_engine: Optional[Engine] = None


def _build_database_url() -> str:
    dialect: str = (settings.DB_DIALECT or "mysql").lower()
    host: str = settings.DB_HOST or ""
    port: str = str(settings.DB_PORT or "")
    user: str = settings.DB_USER or ""
    password: str = settings.DB_PASSWORD or ""
    db_name: str = settings.DB_NAME or ""

    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")  # 直接使用外部提供的完整URL

    password = quote_plus(password)

    if dialect in ("postgresql", "postgres"):
        # PostgreSQL 使用 psycopg2 驱动
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

    # 默认 MySQL 使用 pymysql 驱动（同步）
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url: str = _build_database_url()
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine


def fetch_all(query: str, params: Optional[Union[Iterable[Any], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    执行只读查询并返回字典列表（同步版本）。
    """
    engine: Engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.mappings().all()
        # 将 RowMapping 转换为普通字典
        return [dict(row) for row in rows]


