"""Pydantic API 模式定义与领域对象序列化辅助函数。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..core.constant import Direction, Exchange, Offset, OrderType
from ..core.object import (
    AccountData,
    BarData,
    ContractData,
    LogData,
    OrderData,
    PositionData,
    TickData,
    TradeData,
)

# ----------------------------------------------------------------------
# 请求体
# ----------------------------------------------------------------------


class ConnectRequestBody(BaseModel):
    """Gateway 连接配置（为空 = 使用默认值）。"""

    setting: dict[str, Any] = Field(default_factory=dict)


class SubscribeRequestBody(BaseModel):
    vt_symbols: list[str]


class PlaceOrderBody(BaseModel):
    vt_symbol: str
    direction: Direction
    type: OrderType = OrderType.LIMIT
    volume: float = Field(gt=0)
    price: float = 0
    offset: Offset = Offset.OPEN
    gateway_name: str = ""
    reference: str = ""


class CreateStrategyBody(BaseModel):
    class_name: str
    name: str
    vt_symbol: str = ""
    vt_symbols: list[str] = Field(default_factory=list)
    setting: dict[str, Any] = Field(default_factory=dict)


class EditStrategyBody(BaseModel):
    setting: dict[str, Any]


class WriteStrategyFileBody(BaseModel):
    filename: str
    code: str
    overwrite: bool = False


class ChatMessageBody(BaseModel):
    role: str
    content: Any  # str 或 Anthropic 内容块


class ChatRequestBody(BaseModel):
    messages: list[ChatMessageBody]
    conversation_id: str | None = None
    display_messages: list[dict] | None = None


class AiConfigBody(BaseModel):
    provider: str | None = None    # anthropic | openai
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None     # 为空/None 时保留现有密钥
    allow_trading: bool | None = None
    auto_optimize: bool | None = None


class CtpConfigBody(BaseModel):
    """CTP 账户/服务器配置更新（所有字段均可选）。"""

    userid: str | None = None
    password: str | None = None    # 为空/None 时保留现有密码
    brokerid: str | None = None
    td_address: str | None = None
    md_address: str | None = None
    appid: str | None = None
    auth_code: str | None = None


class StockConfigBody(BaseModel):
    """STOCK gateway 配置更新（所有字段均可选）。"""

    poll_interval: float | None = None


class BacktestRequestBody(BaseModel):
    class_name: str = ""
    class_names: list[str] = Field(default_factory=list)
    vt_symbol: str = ""
    vt_symbols: list[str] = Field(default_factory=list)
    interval: str = "1m"
    start: datetime
    end: datetime | None = None
    capital: float = 1_000_000
    rate: float = 0.0001
    slippage: float = 0
    size: float = 1
    pricetick: float = 0.01
    setting: dict[str, Any] = Field(default_factory=dict)


class DownloadDataBody(BaseModel):
    vt_symbol: str
    interval: str = "1m"
    start: datetime
    end: datetime | None = None
    gateway_name: str = ""


class RiskSettingsBody(BaseModel):
    active: bool | None = None
    order_flow_limit: int | None = None
    order_flow_clear: int | None = None
    order_size_limit: float | None = None
    order_count_limit: int | None = None
    active_order_limit: int | None = None
    trade_count_limit: int | None = None
    position_limit: float | None = None
    daily_loss_limit_pct: float | None = None
    enable_order_size: bool | None = None
    enable_order_flow: bool | None = None
    enable_order_count: bool | None = None
    enable_active_order: bool | None = None
    enable_trade_count: bool | None = None
    enable_position_limit: bool | None = None
    enable_daily_loss_breaker: bool | None = None
    enable_trailing_stop: bool | None = None
    trailing_stops: dict[str, float] | None = None
    enable_order_flow: bool | None = None
    enable_order_count: bool | None = None
    enable_active_order: bool | None = None
    enable_trade_count: bool | None = None
    enable_position_limit: bool | None = None
    enable_daily_loss_breaker: bool | None = None


# ----------------------------------------------------------------------
# 领域数据类序列化 -> JSON 安全字典
# （REST 响应和 WebSocket 推送共同使用）
# ----------------------------------------------------------------------


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_tick(tick: TickData) -> dict:
    data = {
        "vt_symbol": tick.vt_symbol,
        "symbol": tick.symbol,
        "exchange": tick.exchange.value,
        "datetime": _dt(tick.datetime),
        "name": tick.name,
        "volume": tick.volume,
        "turnover": tick.turnover,
        "open_interest": tick.open_interest,
        "last_price": tick.last_price,
        "limit_up": tick.limit_up,
        "limit_down": tick.limit_down,
        "open_price": tick.open_price,
        "high_price": tick.high_price,
        "low_price": tick.low_price,
        "pre_close": tick.pre_close,
        "gateway_name": tick.gateway_name,
    }
    for level in range(1, 6):
        for prefix in ("bid_price", "ask_price", "bid_volume", "ask_volume"):
            key = f"{prefix}_{level}"
            data[key] = getattr(tick, key)
    return data


def serialize_order(order: OrderData) -> dict:
    return {
        "vt_orderid": order.vt_orderid,
        "vt_symbol": order.vt_symbol,
        "symbol": order.symbol,
        "exchange": order.exchange.value,
        "orderid": order.orderid,
        "type": order.type.value,
        "direction": order.direction.value if order.direction else None,
        "offset": order.offset.value,
        "price": order.price,
        "volume": order.volume,
        "traded": order.traded,
        "status": order.status.value,
        "datetime": _dt(order.datetime),
        "reference": order.reference,
        "gateway_name": order.gateway_name,
    }


def serialize_trade(trade: TradeData) -> dict:
    return {
        "vt_tradeid": trade.vt_tradeid,
        "vt_orderid": trade.vt_orderid,
        "vt_symbol": trade.vt_symbol,
        "symbol": trade.symbol,
        "exchange": trade.exchange.value,
        "orderid": trade.orderid,
        "tradeid": trade.tradeid,
        "direction": trade.direction.value if trade.direction else None,
        "offset": trade.offset.value,
        "price": trade.price,
        "volume": trade.volume,
        "datetime": _dt(trade.datetime),
        "gateway_name": trade.gateway_name,
        "pnl": 0.0,  # 在 list_trades 端点中计算
    }


def serialize_position(position: PositionData) -> dict:
    return {
        "vt_positionid": position.vt_positionid,
        "vt_symbol": position.vt_symbol,
        "symbol": position.symbol,
        "exchange": position.exchange.value,
        "direction": position.direction.value,
        "volume": position.volume,
        "frozen": position.frozen,
        "price": position.price,
        "pnl": position.pnl,
        "yd_volume": position.yd_volume,
        "gateway_name": position.gateway_name,
        "datetime": _dt(position.datetime),
    }


def serialize_account(account: AccountData) -> dict:
    return {
        "vt_accountid": account.vt_accountid,
        "accountid": account.accountid,
        "balance": account.balance,
        "frozen": account.frozen,
        "available": account.available,
        "gateway_name": account.gateway_name,
    }


def serialize_contract(contract: ContractData) -> dict:
    return {
        "vt_symbol": contract.vt_symbol,
        "symbol": contract.symbol,
        "exchange": contract.exchange.value,
        "name": contract.name,
        "product": contract.product.value,
        "size": contract.size,
        "pricetick": contract.pricetick,
        "min_volume": contract.min_volume,
        "stop_supported": contract.stop_supported,
        "net_position": contract.net_position,
        "history_data": contract.history_data,
        "gateway_name": contract.gateway_name,
    }


def serialize_log(log: LogData) -> dict:
    return {
        "time": _dt(log.time),
        "level": log.level,
        "msg": log.msg,
        "gateway_name": log.gateway_name,
    }


def serialize_bar(bar: BarData) -> dict:
    return {
        "vt_symbol": bar.vt_symbol,
        "symbol": bar.symbol,
        "exchange": bar.exchange.value,
        "datetime": _dt(bar.datetime),
        "interval": bar.interval.value if bar.interval else None,
        "volume": bar.volume,
        "turnover": bar.turnover,
        "open_interest": bar.open_interest,
        "open_price": bar.open_price,
        "high_price": bar.high_price,
        "low_price": bar.low_price,
        "close_price": bar.close_price,
    }
