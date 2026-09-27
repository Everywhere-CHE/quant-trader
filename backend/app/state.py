"""应用全局状态：集中装配量化引擎栈。

把原先散落在 ``app.main`` lifespan 里的引擎装配 / 网关挂载 / 自动连接 /
后台自启动 / WebSocket 桥接 / AIEngine 全部集中到一个对象，使依赖拓扑
一目了然、可独立实例化测试。``app.main`` 的 lifespan 仅负责实例化 +
``start`` / ``close``。运行时行为与原先完全一致。

为避免 ``app.main`` 与 ``api`` 模块的循环导入，AppState 独立于此模块
（参照版 state.py 同款设计）。``app.state.main_engine`` 等旧属性仍由
lifespan 设置，保证 ``deps.get_main_engine`` 与 AI 路由零改动。
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING

from .config import Settings
from .core.engine import LogEngine, MainEngine, OmsEngine, RiskEngine
from .core.event import EventEngine
from .core.gateway import CtpGateway, StockGateway
from .core.object import SubscribeRequest
from .core.strategy.engine import StrategyEngine
from .core.utility import extract_vt_symbol
from .db.data_engine import DataEngine
from .db.session import dispose_db, init_db
from .services.bar_recorder import BarRecorder
from .api.websocket import ConnectionManager, EventBridge
from .stock_config import load_stock_config
from .watchlist import load_watchlist

if TYPE_CHECKING:
    from .ai.engine import AIEngine


def _start_watchlist_autosubscribe(main_engine: MainEngine) -> None:
    """在对应 Gateway 可用后，订阅自选列表中的每个合约。

    STOCK 代码立即订阅（合约惰性注册）；
    期货合约需等待 CTP 完成登录和合约查询。
    每个合约超过 ``timeout`` 秒后放弃。
    """

    def worker(timeout: float = 120.0) -> None:
        pending: dict[str, tuple[str, object]] = {}
        for vt_symbol in load_watchlist():
            try:
                symbol, exchange = extract_vt_symbol(vt_symbol)
            except ValueError:
                main_engine.write_log(
                    f"watchlist: invalid symbol skipped: {vt_symbol}",
                    source="Watchlist",
                )
                continue
            pending[vt_symbol] = (symbol, exchange)

        deadline = time.monotonic() + timeout
        while pending and time.monotonic() < deadline:
            for vt_symbol in list(pending):
                symbol, exchange = pending[vt_symbol]
                contract = main_engine.oms.get_contract(vt_symbol)
                gateway_name = ""
                if contract:
                    gateway_name = contract.gateway_name
                else:
                    # 路由到任意一个已连接且覆盖该交易所的 Gateway
                    # （STOCK 会惰性注册未知的 A 股代码）。
                    for name, gw in main_engine.gateways.items():
                        if (
                            name != "SIM"
                            and gw.connected
                            and exchange in gw.exchanges
                        ):
                            gateway_name = name
                            break
                if not gateway_name:
                    continue  # Gateway 尚未就绪 — 下一轮重试
                main_engine.subscribe(
                    SubscribeRequest(symbol=symbol, exchange=exchange),
                    gateway_name,
                )
                del pending[vt_symbol]
            if pending:
                time.sleep(1.0)

        if pending:
            main_engine.write_log(
                f"watchlist: no gateway available for {sorted(pending)} "
                f"(will subscribe when added again or gateway connects)",
                source="Watchlist",
            )

    threading.Thread(
        target=worker, name="WatchlistAutoSubscribe", daemon=True
    ).start()


def _start_auto_strategies(strategy_engine: StrategyEngine) -> None:
    """在后台线程中延迟启动标记为自动启动的策略。

    等待网关连接后再初始化/启动，确保行情订阅可用。
    """

    def worker() -> None:
        time.sleep(5)  # 简短等待后交给 auto_start_strategies 内部等待合约
        strategy_engine.auto_start_strategies()

    threading.Thread(
        target=worker, name="AutoStartStrategies", daemon=True
    ).start()


class AppState:
    """应用全局状态，挂载到 ``app.state.qt``。"""

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.event_engine: EventEngine = EventEngine()
        self.main_engine: MainEngine = MainEngine(self.event_engine)
        self.ws_manager: ConnectionManager = ConnectionManager()
        self.event_bridge: EventBridge = EventBridge()
        self._broadcaster_task: asyncio.Task | None = None
        # 引擎在 start() 中按序注册
        self.strategy_engine: StrategyEngine | None = None
        self.ai_engine: "AIEngine | None" = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """启动引擎栈、网关、WS 桥接、后台自启动、AI 助手。"""
        # 1. 数据库
        init_db()

        # 2. 量化核心（引擎顺序：log -> oms -> data -> bar_recorder -> risk -> strategy）
        self.main_engine.add_engine(LogEngine)
        self.main_engine.add_engine(OmsEngine)
        self.main_engine.add_engine(DataEngine)
        self.main_engine.add_engine(BarRecorder)
        self.main_engine.add_engine(RiskEngine)
        self.strategy_engine = self.main_engine.add_engine(StrategyEngine)

        # 网关：STOCK 行情 + CTP 期货（均为真实数据网关）
        if self.settings.enable_stock_gateway:
            self.main_engine.add_gateway(StockGateway)
        if self.settings.enable_ctp_gateway and CtpGateway is not None:
            self.main_engine.add_gateway(CtpGateway)
        self.main_engine.start(loop)

        # 恢复已持久化的策略实例（始终处于 STOPPED 状态）
        assert self.strategy_engine is not None
        self.strategy_engine.load_strategies_from_db()

        # 3. WebSocket 桥接（事件线程 -> asyncio）
        self.event_bridge.start(self.event_engine, loop)
        self._broadcaster_task = asyncio.create_task(
            self.event_bridge.broadcaster(self.ws_manager)
        )

        # 4. 自动连接：真实数据 Gateway 默认在启动时连接
        if self.settings.enable_stock_gateway and self.settings.auto_connect_stock:
            self.main_engine.connect(
                load_stock_config(self.settings), StockGateway.default_name
            )
        if (
            self.settings.enable_ctp_gateway
            and CtpGateway is not None
            and self.settings.auto_connect_ctp
        ):
            from .ctp_config import load_ctp_config

            self.main_engine.connect(
                load_ctp_config(self.settings), CtpGateway.default_name
            )

        # 4b. 自动订阅已持久化的自选列表（CTP 合约异步登录后才可用）
        _start_watchlist_autosubscribe(self.main_engine)

        # 4c. 自动启动标记了 auto_start 的策略（延迟 5s 等网关连上）
        _start_auto_strategies(self.strategy_engine)

        # 5. AI 助手（未配置 API key 时零开销）
        from .ai.engine import AIEngine

        self.ai_engine = AIEngine(self.settings)

    async def close(self) -> None:
        """关闭：先停止广播任务，再停止引擎栈，最后释放数据库。"""
        if self._broadcaster_task is not None:
            self._broadcaster_task.cancel()
            try:
                await self._broadcaster_task
            except asyncio.CancelledError:
                pass
        self.main_engine.close()
        dispose_db()


def get_state(request) -> "AppState":
    """FastAPI 依赖：获取应用全局状态。"""
    return request.app.state.qt
