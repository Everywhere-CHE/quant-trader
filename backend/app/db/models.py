"""SQLAlchemy ORM 模型。

按照 CLAUDE.md 要求建表：accounts、orders、trades、positions、
ticks、strategies，另加 bars（用于回测）和 contracts（便于前端
在重启后仍能列出合约）。

约定：
- 枚举以 String 存储（其英文 ``.value``）；
- 日期时间以不带时区的 Asia/Shanghai 时间存储；
- 已设置命名约定，便于后续 Alembic 接管而无需重命名。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AccountModel(TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("gateway_name", "accountid"),)

    gateway_name: Mapped[str] = mapped_column(String(32))
    accountid: Mapped[str] = mapped_column(String(64))
    balance: Mapped[float] = mapped_column(Float, default=0)
    frozen: Mapped[float] = mapped_column(Float, default=0)


class OrderModel(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("gateway_name", "orderid"),
        Index("ix_orders_symbol_exchange", "symbol", "exchange"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_datetime", "datetime"),
    )

    gateway_name: Mapped[str] = mapped_column(String(32))
    orderid: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    offset: Mapped[str] = mapped_column(String(16), default="NONE")
    price: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[float] = mapped_column(Float, default=0)
    traded: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16))
    datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reference: Mapped[str] = mapped_column(String(128), default="")


class TradeModel(TimestampMixin, Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("gateway_name", "tradeid"),
        Index("ix_trades_symbol_exchange", "symbol", "exchange"),
        Index("ix_trades_datetime", "datetime"),
    )

    gateway_name: Mapped[str] = mapped_column(String(32))
    tradeid: Mapped[str] = mapped_column(String(64))
    orderid: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    offset: Mapped[str] = mapped_column(String(16), default="NONE")
    price: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[float] = mapped_column(Float, default=0)
    datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PositionModel(TimestampMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("gateway_name", "symbol", "exchange", "direction"),
    )

    gateway_name: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    volume: Mapped[float] = mapped_column(Float, default=0)
    frozen: Mapped[float] = mapped_column(Float, default=0)
    price: Mapped[float] = mapped_column(Float, default=0)
    pnl: Mapped[float] = mapped_column(Float, default=0)
    yd_volume: Mapped[float] = mapped_column(Float, default=0)


class TickModel(TimestampMixin, Base):
    __tablename__ = "ticks"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "datetime"),
        Index("ix_ticks_symbol_exchange_datetime", "symbol", "exchange", "datetime"),
    )

    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    datetime: Mapped[datetime] = mapped_column(DateTime)
    name: Mapped[str] = mapped_column(String(64), default="")
    volume: Mapped[float] = mapped_column(Float, default=0)
    turnover: Mapped[float] = mapped_column(Float, default=0)
    open_interest: Mapped[float] = mapped_column(Float, default=0)
    last_price: Mapped[float] = mapped_column(Float, default=0)
    limit_up: Mapped[float] = mapped_column(Float, default=0)
    limit_down: Mapped[float] = mapped_column(Float, default=0)
    open_price: Mapped[float] = mapped_column(Float, default=0)
    high_price: Mapped[float] = mapped_column(Float, default=0)
    low_price: Mapped[float] = mapped_column(Float, default=0)
    pre_close: Mapped[float] = mapped_column(Float, default=0)

    bid_price_1: Mapped[float] = mapped_column(Float, default=0)
    bid_price_2: Mapped[float] = mapped_column(Float, default=0)
    bid_price_3: Mapped[float] = mapped_column(Float, default=0)
    bid_price_4: Mapped[float] = mapped_column(Float, default=0)
    bid_price_5: Mapped[float] = mapped_column(Float, default=0)
    ask_price_1: Mapped[float] = mapped_column(Float, default=0)
    ask_price_2: Mapped[float] = mapped_column(Float, default=0)
    ask_price_3: Mapped[float] = mapped_column(Float, default=0)
    ask_price_4: Mapped[float] = mapped_column(Float, default=0)
    ask_price_5: Mapped[float] = mapped_column(Float, default=0)
    bid_volume_1: Mapped[float] = mapped_column(Float, default=0)
    bid_volume_2: Mapped[float] = mapped_column(Float, default=0)
    bid_volume_3: Mapped[float] = mapped_column(Float, default=0)
    bid_volume_4: Mapped[float] = mapped_column(Float, default=0)
    bid_volume_5: Mapped[float] = mapped_column(Float, default=0)
    ask_volume_1: Mapped[float] = mapped_column(Float, default=0)
    ask_volume_2: Mapped[float] = mapped_column(Float, default=0)
    ask_volume_3: Mapped[float] = mapped_column(Float, default=0)
    ask_volume_4: Mapped[float] = mapped_column(Float, default=0)
    ask_volume_5: Mapped[float] = mapped_column(Float, default=0)


class BarModel(TimestampMixin, Base):
    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "interval", "datetime"),
        Index(
            "ix_bars_symbol_exchange_interval_datetime",
            "symbol",
            "exchange",
            "interval",
            "datetime",
        ),
    )

    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    interval: Mapped[str] = mapped_column(String(8))
    datetime: Mapped[datetime] = mapped_column(DateTime)
    volume: Mapped[float] = mapped_column(Float, default=0)
    turnover: Mapped[float] = mapped_column(Float, default=0)
    open_interest: Mapped[float] = mapped_column(Float, default=0)
    open_price: Mapped[float] = mapped_column(Float, default=0)
    high_price: Mapped[float] = mapped_column(Float, default=0)
    low_price: Mapped[float] = mapped_column(Float, default=0)
    close_price: Mapped[float] = mapped_column(Float, default=0)


class ContractModel(TimestampMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("symbol", "exchange", "gateway_name"),)

    gateway_name: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64), default="")
    product: Mapped[str] = mapped_column(String(16))
    size: Mapped[float] = mapped_column(Float, default=1)
    pricetick: Mapped[float] = mapped_column(Float, default=0)
    min_volume: Mapped[float] = mapped_column(Float, default=1)


class StrategyModel(TimestampMixin, Base):
    """策略注册表（从第三阶段开始使用；现在先建表）。"""

    __tablename__ = "strategies"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    class_name: Mapped[str] = mapped_column(String(128))
    vt_symbols: Mapped[str] = mapped_column(Text, default="[]")  # JSON 列表
    setting: Mapped[str] = mapped_column(Text, default="{}")     # JSON 字典
    status: Mapped[str] = mapped_column(String(16), default="STOPPED")
    # 每次成交时同步的运行时变量（如 pos 等），使持仓在重启后
    # 仍能保留 —— 等同于 vn.py 的 cta_strategy_data.json。
    variables: Mapped[str] = mapped_column(Text, default="{}")   # JSON 字典
    # 是否在项目启动时自动初始化并启动
    auto_start: Mapped[bool] = mapped_column(Boolean, default=False)
