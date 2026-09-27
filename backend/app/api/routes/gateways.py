"""网关管理端点。"""

from fastapi import APIRouter, Depends, HTTPException

from ...config import get_settings
from ...core.engine.main_engine import MainEngine
from ...core.object import SubscribeRequest
from ...core.utility import extract_vt_symbol
from ...ctp_config import (
    CTP_SERVER_PRESETS,
    load_ctp_config,
    masked,
    save_ctp_config,
)
from ...stock_config import load_stock_config, save_stock_config
from ..deps import get_main_engine
from ..schemas import (ConnectRequestBody, CtpConfigBody, StockConfigBody, SubscribeRequestBody)

router = APIRouter(prefix="/gateways", tags=["gateways"])

SENSITIVE_KEYWORDS = ("password", "secret", "token", "auth")


def _mask_setting(setting: dict) -> dict:
    """返回前对配置结构中的敏感字段进行脱敏。"""
    result = {}
    for key, value in setting.items():
        if any(word in key.lower() for word in SENSITIVE_KEYWORDS):
            result[key] = "***"
        else:
            result[key] = value
    return result


@router.get("")
def list_gateways(
    main_engine: MainEngine = Depends(get_main_engine),
) -> list[dict]:
    result = []
    for name, gateway in main_engine.gateways.items():
        result.append(
            {
                "name": name,
                "connected": gateway.connected,
                "default_setting": _mask_setting(gateway.get_default_setting()),
                "exchanges": [ex.value for ex in gateway.exchanges],
            }
        )
    return result


# ----------------------------------------------------------------------
# CTP 连接配置（运行时可编辑并持久化；支持 SimNow 或真实
# 期货公司柜台）。注意：必须声明在 /{gateway_name} 路径之前。
# ----------------------------------------------------------------------


@router.get("/ctp/config")
def get_ctp_config() -> dict:
    """当前生效的 CTP 配置（密码已脱敏）。"""
    return masked(load_ctp_config(get_settings()))


@router.get("/ctp/presets")
def get_ctp_presets() -> list[dict]:
    """常见 CTP 服务器预设（SimNow / openctp TTS / 实盘）。"""
    return CTP_SERVER_PRESETS


@router.put("/ctp/config")
def update_ctp_config(body: CtpConfigBody) -> dict:
    """更新已持久化的 CTP 账户/服务器配置。

    密码为空时保留原有密码。配置在下次连接时生效；
    如当前已连接，请在设置页面断开并重新连接以切换账户。
    """
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    config = save_ctp_config(get_settings(), updates)
    return masked(config)


# ----------------------------------------------------------------------
# STOCK 网关配置（运行时可编辑）
# ----------------------------------------------------------------------


@router.get("/stock/config")
def get_stock_config() -> dict:
    """当前生效的 STOCK 网关配置。"""
    cfg = load_stock_config(get_settings())
    return {
        "poll_interval": cfg.get("poll_interval", 3.0),
    }


@router.put("/stock/config")
def update_stock_config(body: StockConfigBody) -> dict:
    """更新已持久化的 STOCK 网关配置。"""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    config = save_stock_config(get_settings(), updates)
    return config


@router.post("/{gateway_name}/connect", status_code=202)
def connect_gateway(
    gateway_name: str,
    body: ConnectRequestBody | None = None,
    main_engine: MainEngine = Depends(get_main_engine),
) -> dict:
    gateway = main_engine.gateways.get(gateway_name)
    if not gateway:
        raise HTTPException(404, f"Gateway not found: {gateway_name}")

    setting = body.setting if body else {}
    # 对于 CTP，请求体为空时使用已持久化的运行时配置
    # （其本身会回退到 .env），因此密码永远不会经由
    # HTTP 请求传输。
    if gateway_name == "CTP" and not setting:
        setting = load_ctp_config(get_settings())
    if gateway_name == "STOCK" and not setting:
        setting = load_stock_config(get_settings())
    main_engine.connect(setting, gateway_name)

    # 重新执行自选列表的自动订阅，让待订阅的合约（如等待 CTP
    # 合约信息的期货）在本次连接后开始推送行情。
    from ...state import _start_watchlist_autosubscribe

    _start_watchlist_autosubscribe(main_engine)
    return {"accepted": True, "gateway_name": gateway_name}


@router.post("/{gateway_name}/disconnect", status_code=202)
def disconnect_gateway(
    gateway_name: str,
    main_engine: MainEngine = Depends(get_main_engine),
) -> dict:
    """关闭网关连接（例如在切换 CTP 账户之前）。"""
    gateway = main_engine.gateways.get(gateway_name)
    if not gateway:
        raise HTTPException(404, f"Gateway not found: {gateway_name}")
    if not gateway.connected:
        return {"accepted": True, "gateway_name": gateway_name,
                "note": "already disconnected"}
    gateway.close()
    return {"accepted": True, "gateway_name": gateway_name}


@router.post("/{gateway_name}/subscribe", status_code=202)
def subscribe(
    gateway_name: str,
    body: SubscribeRequestBody,
    main_engine: MainEngine = Depends(get_main_engine),
) -> dict:
    gateway = main_engine.gateways.get(gateway_name)
    if not gateway:
        raise HTTPException(404, f"Gateway not found: {gateway_name}")
    if not gateway.connected:
        raise HTTPException(409, f"Gateway not connected: {gateway_name}")

    subscribed = []
    for vt_symbol in body.vt_symbols:
        try:
            symbol, exchange = extract_vt_symbol(vt_symbol)
        except ValueError:
            raise HTTPException(422, f"Invalid vt_symbol: {vt_symbol}") from None
        main_engine.subscribe(
            SubscribeRequest(symbol=symbol, exchange=exchange), gateway_name
        )
        subscribed.append(vt_symbol)
    return {"accepted": True, "vt_symbols": subscribed}
