"""共享交易工具层。

同一套实现同时被 MCP 服务器（独立进程）和应用内的 AIEngine 使用：
每个工具都是对平台 REST API 的一次 HTTP 调用，因此无论调用方是谁，
行为都完全一致。

``TOOL_SPECS`` 是工具 schema 的唯一真实来源：MCP 服务器和
Anthropic tool-use 循环都从中注册。

输出是紧凑的、对 LLM 友好的摘要（不含完整的五档深度，也不含
完整的 daily_results 数组）。
"""

import json
import os
from typing import Any

import httpx

# 可通过环境变量 QT_API_BASE 覆盖，默认 127.0.0.1:8000
DEFAULT_BASE_URL = os.environ.get("QT_API_BASE", "http://127.0.0.1:8000/api")


class ToolExecutionError(Exception):
    """工具级错误，其消息旨在供 LLM 阅读。"""


class TradingTools:
    """基于平台 REST API 的同步工具实现。"""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        allow_trading: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=120)
        self.allow_trading = allow_trading

    # ------------------------------------------------------------------
    # HTTP 辅助方法
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = self.client.get(f"{self.base_url}{path}", params=params)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, body: dict | None = None) -> Any:
        resp = self.client.post(f"{self.base_url}{path}", json=body or {})
        self._raise_for_status(resp)
        return resp.json()

    def _put(self, path: str, body: dict) -> Any:
        resp = self.client.put(f"{self.base_url}{path}", json=body)
        self._raise_for_status(resp)
        return resp.json()

    def _delete(self, path: str) -> Any:
        resp = self.client.delete(f"{self.base_url}{path}")
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolExecutionError(f"接口错误 {resp.status_code}: {detail}")

    def _check_trading_allowed(self) -> None:
        if not self.allow_trading:
            raise ToolExecutionError(
                "AI 交易未启用（AI_ALLOW_TRADING=false）。只能提供分析和建议，"
                "不能直接下单/撤单。用户可在 backend/.env 中开启。"
            )

    # ------------------------------------------------------------------
    # 只读：行情 / 持仓账户
    # ------------------------------------------------------------------

    def get_market_overview(self, gateway: str = "", limit: int = 30) -> dict:
        contracts = self._get("/contracts", {"gateway": gateway} if gateway else None)
        ticks = {t["vt_symbol"]: t for t in self._get("/ticks")}
        rows = []
        for c in contracts[: max(1, limit)]:
            tick = ticks.get(c["vt_symbol"])
            last = tick["last_price"] if tick else 0
            pre = tick["pre_close"] if tick else 0
            chg = round((last - pre) / pre * 100, 2) if pre else 0
            rows.append(
                {
                    "vt_symbol": c["vt_symbol"],
                    "name": c["name"],
                    "product": c["product"],
                    "last": last,
                    "chg_pct": chg,
                    "volume": tick["volume"] if tick else 0,
                }
            )
        return {"count": len(rows), "contracts": rows}

    def get_tick(self, vt_symbol: str) -> dict:
        t = self._get(f"/ticks/{vt_symbol}")
        return {
            "vt_symbol": t["vt_symbol"],
            "name": t["name"],
            "time": t["datetime"],
            "last": t["last_price"],
            "open": t["open_price"],
            "high": t["high_price"],
            "low": t["low_price"],
            "pre_close": t["pre_close"],
            "volume": t["volume"],
            "bid1": t["bid_price_1"],
            "bid1_vol": t["bid_volume_1"],
            "ask1": t["ask_price_1"],
            "ask1_vol": t["ask_volume_1"],
            "limit_up": t["limit_up"],
            "limit_down": t["limit_down"],
        }

    def get_bars(
        self,
        vt_symbol: str,
        interval: str = "1m",
        limit: int = 100,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        params: dict = {"vt_symbol": vt_symbol, "interval": interval}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        bars = self._get("/bars", params)
        if not bars:
            return {"count": 0, "bars": [], "hint": "无数据；可先调用 download_backtest_data"}
        tail = bars[-max(1, limit):]
        return {
            "count": len(bars),
            "first": bars[0]["datetime"],
            "last": bars[-1]["datetime"],
            "returned": len(tail),
            "columns": ["datetime", "open", "high", "low", "close", "volume"],
            "bars": [
                [
                    b["datetime"],
                    b["open_price"],
                    b["high_price"],
                    b["low_price"],
                    b["close_price"],
                    b["volume"],
                ]
                for b in tail
            ],
        }

    def get_positions(self) -> list[dict]:
        return [
            {
                "vt_symbol": p["vt_symbol"],
                "direction": p["direction"],
                "volume": p["volume"],
                "price": p["price"],
                "pnl": p["pnl"],
                "yd_volume": p["yd_volume"],
            }
            for p in self._get("/positions")
            if p["volume"]
        ]

    def get_accounts(self) -> list[dict]:
        return [
            {
                "accountid": a["vt_accountid"],
                "balance": a["balance"],
                "available": a["available"],
                "frozen": a["frozen"],
            }
            for a in self._get("/accounts")
        ]

    def get_orders(
        self, active_only: bool = False, vt_symbol: str = "", limit: int = 20
    ) -> list[dict]:
        params: dict = {"active_only": active_only}
        if vt_symbol:
            params["vt_symbol"] = vt_symbol
        orders = self._get("/orders", params)
        orders.sort(key=lambda o: o.get("datetime") or "", reverse=True)
        return [
            {
                "vt_orderid": o["vt_orderid"],
                "vt_symbol": o["vt_symbol"],
                "direction": o["direction"],
                "offset": o["offset"],
                "price": o["price"],
                "volume": o["volume"],
                "traded": o["traded"],
                "status": o["status"],
                "time": o["datetime"],
            }
            for o in orders[: max(1, limit)]
        ]

    def get_trades(self, vt_symbol: str = "", limit: int = 20) -> list[dict]:
        params: dict = {}
        if vt_symbol:
            params["vt_symbol"] = vt_symbol
        trades = self._get("/trades", params)
        # 接口已按时间倒序返回（最新在前）
        return [
            {
                "vt_tradeid": t["vt_tradeid"],
                "vt_symbol": t["vt_symbol"],
                "direction": t["direction"],
                "offset": t["offset"],
                "price": t["price"],
                "volume": t["volume"],
                "pnl": t.get("pnl", 0),
                "fee": t.get("fee", 0),
                "time": t["datetime"],
            }
            for t in trades[: max(1, limit)]
        ]

    def get_performance(self, hours: int = 24) -> dict:
        """最近 N 小时的交易绩效摘要（胜率/盈亏/手续费/持仓浮盈）。"""
        result = self._get("/backtest/performance", {"hours": hours})
        # 明细行数较多时截断，只保留摘要 + 最近 10 笔
        result["trades"] = result.get("trades", [])[:10]
        return result

    def get_intraday_bars(
        self, vt_symbol: str, interval: str = "1m", limit: int = 120
    ) -> dict:
        """盘中实时K线（由真实收到的 Tick 合成；1h/d/w 会拼接历史）。"""
        bars = self._get(
            "/bars/intraday",
            {"vt_symbol": vt_symbol, "interval": interval, "limit": limit},
        )
        if not bars:
            return {
                "count": 0,
                "bars": [],
                "hint": "无盘中数据；请确认该合约已订阅且有行情推送",
            }
        return {
            "count": len(bars),
            "columns": ["datetime", "open", "high", "low", "close", "volume"],
            "bars": [
                [
                    b["datetime"],
                    b["open_price"],
                    b["high_price"],
                    b["low_price"],
                    b["close_price"],
                    b["volume"],
                ]
                for b in bars[-max(1, limit):]
            ],
        }

    def get_gateways(self) -> list[dict]:
        """各网关的连接状态与支持的交易所。"""
        return [
            {
                "name": g["name"],
                "connected": g["connected"],
                "exchanges": g["exchanges"],
            }
            for g in self._get("/gateways")
        ]

    def get_logs(self, limit: int = 30, keyword: str = "") -> list[dict]:
        """最近的系统日志（可按关键字过滤），用于排查连接/风控/策略问题。"""
        logs = self._get("/logs", {"limit": max(limit, 100)})
        if keyword:
            logs = [log for log in logs if keyword.lower() in log["msg"].lower()]
        return [
            {"time": log["time"], "source": log["gateway_name"], "msg": log["msg"]}
            for log in logs[: max(1, limit)]
        ]

    # ------------------------------------------------------------------
    # 交易（受限）
    # ------------------------------------------------------------------

    def place_order(
        self,
        vt_symbol: str,
        direction: str,
        volume: float,
        price: float = 0,
        offset: str = "OPEN",
        order_type: str = "LIMIT",
    ) -> dict:
        self._check_trading_allowed()
        return self._post(
            "/orders",
            {
                "vt_symbol": vt_symbol,
                "direction": direction,
                "offset": offset,
                "type": order_type,
                "price": price,
                "volume": volume,
            },
        )

    def cancel_order(self, vt_orderid: str) -> dict:
        """撤销委托（仅撤单，不开新仓，风险较低，不受 AI_ALLOW_TRADING 限制）。"""
        return self._delete(f"/orders/{vt_orderid}")

    # ------------------------------------------------------------------
    # 策略
    # ------------------------------------------------------------------

    def list_strategies(self) -> list[dict]:
        return [
            {
                "name": s["strategy_name"],
                "class_name": s["class_name"],
                "vt_symbol": s["vt_symbol"],
                "inited": s["variables"].get("inited"),
                "trading": s["variables"].get("trading"),
                "pos": s["variables"].get("pos"),
                "parameters": s["parameters"],
            }
            for s in self._get("/strategies")
        ]

    def list_strategy_classes(self) -> list[dict]:
        return self._get("/strategies/classes")

    def create_strategy(
        self,
        class_name: str,
        name: str,
        vt_symbol: str,
        setting: dict | None = None,
    ) -> dict:
        return self._post(
            "/strategies",
            {
                "class_name": class_name,
                "name": name,
                "vt_symbol": vt_symbol,
                "setting": setting or {},
            },
        )

    def control_strategy(self, name: str, action: str) -> dict:
        if action not in ("init", "start", "stop"):
            raise ToolExecutionError(
                f"未知操作 {action!r}，必须是 init/start/stop"
            )
        return self._post(f"/strategies/{name}/{action}")

    def edit_strategy(self, name: str, setting: dict) -> dict:
        """修改策略实例参数（运行中的策略需先停止才生效于下一根K线）。"""
        return self._put(f"/strategies/{name}", {"setting": setting})

    def read_strategy_file(self, filename: str) -> dict:
        """读取用户策略目录中某个 .py 文件的完整源码。"""
        return self._get(f"/strategies/files/{filename}")

    def list_strategy_files(self) -> list[dict]:
        """列出用户策略目录下的全部 .py 文件。"""
        return self._get("/strategies/files")

    def reconcile_positions(self) -> list[dict]:
        """策略 pos 与网关净持仓对账，返回每个策略的差异行。"""
        return self._get("/strategies/reconcile")

    def sync_strategy_pos(self, name: str) -> dict:
        """把策略 pos 同步为网关净持仓（需策略已停止且合约未被共用）。"""
        self._check_trading_allowed()
        return self._post(f"/strategies/{name}/sync-pos")

    def write_strategy_file(
        self, filename: str, code: str, overwrite: bool = False
    ) -> dict:
        return self._post(
            "/strategies/files",
            {"filename": filename, "code": code, "overwrite": overwrite},
        )

    def reload_strategies(self) -> dict:
        return self._post("/strategies/reload")

    # ------------------------------------------------------------------
    # 回测
    # ------------------------------------------------------------------

    def run_backtest(
        self,
        class_name: str,
        vt_symbol: str,
        start: str,
        end: str | None = None,
        interval: str = "1m",
        capital: float = 1_000_000,
        rate: float = 0.0001,
        slippage: float = 0,
        size: float = 1,
        pricetick: float = 0.01,
        setting: dict | None = None,
    ) -> dict:
        body: dict = {
            "class_name": class_name,
            "vt_symbol": vt_symbol,
            "interval": interval,
            "start": start,
            "capital": capital,
            "rate": rate,
            "slippage": slippage,
            "size": size,
            "pricetick": pricetick,
            "setting": setting or {},
        }
        if end:
            body["end"] = end
        result = self._post("/backtest", body)
        trades = result.get("trades", [])
        # 该 API 以列表形式返回统计（每个 策略 x 合约 组合一条）；
        # 本工具只运行单个组合，因此为模型将其扁平化。
        stats = result.get("statistics", [])
        if isinstance(stats, list):
            stats = stats[0] if stats else {}
        return {
            "statistics": stats,
            "trade_count": len(trades),
            "sample_trades": [
                {
                    "time": t["datetime"],
                    "direction": t["direction"],
                    "offset": t["offset"],
                    "price": t["price"],
                    "volume": t["volume"],
                }
                for t in trades[:10]
            ],
        }

    def download_backtest_data(
        self,
        vt_symbol: str,
        start: str,
        end: str | None = None,
        interval: str = "1m",
        gateway_name: str = "SIM",
    ) -> dict:
        body: dict = {
            "vt_symbol": vt_symbol,
            "interval": interval,
            "start": start,
            "gateway_name": gateway_name,
        }
        if end:
            body["end"] = end
        return self._post("/backtest/download-data", body)

    # ------------------------------------------------------------------
    # 风控
    # ------------------------------------------------------------------

    def get_risk_settings(self) -> dict:
        return self._get("/risk")

    def update_risk_settings(self, updates: dict) -> dict:
        return self._put("/risk", updates)


# ----------------------------------------------------------------------
# 工具 schema（MCP 服务器 + Anthropic 工具的唯一真实来源）
# ----------------------------------------------------------------------

def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


_S = {"type": "string"}
_N = {"type": "number"}
_I = {"type": "integer"}
_B = {"type": "boolean"}
_D = {"type": "object"}

TOOL_SPECS: list[dict] = [
    {
        "name": "get_market_overview",
        "description": "获取市场行情总览：所有合约的最新价、涨跌幅、成交量。",
        "input_schema": _obj(
            {"gateway": {**_S, "description": "过滤网关名(SIM/STOCK/CTP)，空=全部"},
             "limit": {**_I, "description": "最多返回条数，默认30"}}),
        "readonly": True,
    },
    {
        "name": "get_tick",
        "description": "获取单个合约的最新行情快照（最新价/开高低/买卖一档/涨跌停）。",
        "input_schema": _obj(
            {"vt_symbol": {**_S, "description": "如 IF2509.CFFEX、600519.SSE"}},
            ["vt_symbol"]),
        "readonly": True,
    },
    {
        "name": "get_bars",
        "description": "获取历史K线（紧凑数组 [datetime,open,high,low,close,volume]）。数据库无数据时提示先下载。",
        "input_schema": _obj(
            {"vt_symbol": _S,
             "interval": {**_S, "enum": ["1m", "1h", "d", "w"], "description": "K线周期"},
             "limit": {**_I, "description": "返回最近N根，默认100"},
             "start": {**_S, "description": "起始时间 ISO 格式，可选"},
             "end": {**_S, "description": "结束时间，可选"}},
            ["vt_symbol"]),
        "readonly": True,
    },
    {
        "name": "get_positions",
        "description": "获取当前所有持仓（合约/方向/数量/均价/盈亏）。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "get_accounts",
        "description": "获取账户资金（权益/可用/冻结）。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "get_orders",
        "description": "获取委托列表（最新在前）。",
        "input_schema": _obj(
            {"active_only": {**_B, "description": "只看活动委托"},
             "vt_symbol": {**_S, "description": "按合约过滤，可选"},
             "limit": {**_I, "description": "最多条数，默认20"}}),
        "readonly": True,
    },
    {
        "name": "get_trades",
        "description": "获取成交记录（最新在前，含逐笔平仓盈亏与手续费）。",
        "input_schema": _obj(
            {"vt_symbol": {**_S, "description": "按合约过滤，可选"},
             "limit": {**_I, "description": "最多条数，默认20"}}),
        "readonly": True,
    },
    {
        "name": "get_performance",
        "description": "最近N小时交易绩效摘要：总盈亏/胜率/手续费/未实现盈亏/涉及合约。",
        "input_schema": _obj(
            {"hours": {**_I, "description": "统计最近多少小时，默认24"}}),
        "readonly": True,
    },
    {
        "name": "get_intraday_bars",
        "description": "获取盘中实时K线（真实Tick合成，非历史库）。适合分析当天日内走势。",
        "input_schema": _obj(
            {"vt_symbol": _S,
             "interval": {**_S, "enum": ["1m", "5m", "15m", "30m", "1h", "d", "w"]},
             "limit": {**_I, "description": "最近N根，默认120"}},
            ["vt_symbol"]),
        "readonly": True,
    },
    {
        "name": "get_gateways",
        "description": "查看各网关（SIM/STOCK/CTP）连接状态与支持的交易所。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "get_logs",
        "description": "查看最近系统日志（连接/风控/策略/异常），可按关键字过滤。用于排查问题。",
        "input_schema": _obj(
            {"limit": {**_I, "description": "最多条数，默认30"},
             "keyword": {**_S, "description": "过滤关键字，可选"}}),
        "readonly": True,
    },
    {
        "name": "place_order",
        "description": "下单（受 AI_ALLOW_TRADING 配置与风控引擎约束）。direction: LONG=买/SHORT=卖；offset: OPEN=开仓/CLOSE=平仓。",
        "input_schema": _obj(
            {"vt_symbol": _S,
             "direction": {**_S, "enum": ["LONG", "SHORT"]},
             "volume": {**_N, "description": "数量(手)"},
             "price": {**_N, "description": "限价单价格；市价单填0"},
             "offset": {**_S, "enum": ["OPEN", "CLOSE", "CLOSETODAY", "CLOSEYESTERDAY"]},
             "order_type": {**_S, "enum": ["LIMIT", "MARKET"]}},
            ["vt_symbol", "direction", "volume"]),
        "readonly": False,
    },
    {
        "name": "cancel_order",
        "description": "撤销活动委托（受 AI_ALLOW_TRADING 约束）。",
        "input_schema": _obj({"vt_orderid": {**_S, "description": "如 SIM.3"}}, ["vt_orderid"]),
        "readonly": False,
    },
    {
        "name": "list_strategies",
        "description": "列出所有策略实例及其状态（inited/trading/pos/参数）。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "list_strategy_classes",
        "description": "列出可用策略类及其参数默认值。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "create_strategy",
        "description": "创建策略实例。",
        "input_schema": _obj(
            {"class_name": _S, "name": {**_S, "description": "实例名，唯一"},
             "vt_symbol": _S, "setting": {**_D, "description": "参数覆盖，可选"}},
            ["class_name", "name", "vt_symbol"]),
        "readonly": False,
    },
    {
        "name": "control_strategy",
        "description": "控制策略生命周期：init(初始化)/start(启动)/stop(停止)。",
        "input_schema": _obj(
            {"name": _S, "action": {**_S, "enum": ["init", "start", "stop"]}},
            ["name", "action"]),
        "readonly": False,
    },
    {
        "name": "edit_strategy",
        "description": "修改策略实例的参数（如均线周期、开仓手数）。建议先停止策略再修改。",
        "input_schema": _obj(
            {"name": {**_S, "description": "策略实例名"},
             "setting": {**_D, "description": "要修改的参数键值对"}},
            ["name", "setting"]),
        "readonly": False,
    },
    {
        "name": "list_strategy_files",
        "description": "列出用户策略目录下全部 .py 源码文件。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "read_strategy_file",
        "description": "读取某个策略文件的完整 Python 源码，用于解释或修改现有策略。",
        "input_schema": _obj(
            {"filename": {**_S, "description": "如 my_rsi_strategy.py"}},
            ["filename"]),
        "readonly": True,
    },
    {
        "name": "reconcile_positions",
        "description": "策略持仓对账：比较每个策略的 pos 与网关净持仓，找出不一致（如策略停止期间的手动交易）。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "sync_strategy_pos",
        "description": "把策略 pos 覆盖为网关净持仓（对账发现差异后使用；需策略已停止、合约未被多策略共用；受 AI_ALLOW_TRADING 约束）。",
        "input_schema": _obj(
            {"name": {**_S, "description": "策略实例名"}}, ["name"]),
        "readonly": False,
    },
    {
        "name": "write_strategy_file",
        "description": (
            "把策略 Python 源码写入用户策略目录并自动重载。代码必须定义 StrategyTemplate 子类，"
            "导入路径：from app.core.strategy.template import StrategyTemplate；"
            "可用 from app.core.strategy.array_manager import ArrayManager 等。"
            "禁止 import os/sys/subprocess 等系统模块。写入成功后可直接用 run_backtest 验证。"
        ),
        "input_schema": _obj(
            {"filename": {**_S, "description": "如 my_strategy.py（字母开头，不含路径）"},
             "code": {**_S, "description": "完整 Python 源码"},
             "overwrite": {**_B, "description": "覆盖已存在文件"}},
            ["filename", "code"]),
        "readonly": False,
    },
    {
        "name": "reload_strategies",
        "description": "重新扫描策略目录，刷新可用策略类列表。",
        "input_schema": _obj({}),
        "readonly": False,
    },
    {
        "name": "run_backtest",
        "description": "运行策略回测，返回统计指标（年化/回撤/夏普/胜率/盈亏比）与前10笔成交。需要数据库中已有对应区间的K线数据（无数据时先 download_backtest_data）。",
        "input_schema": _obj(
            {"class_name": _S, "vt_symbol": _S,
             "start": {**_S, "description": "回测开始时间，如 2026-07-02T09:00:00"},
             "end": {**_S, "description": "结束时间，可选"},
             "interval": {**_S, "enum": ["1m", "1h", "d"]},
             "capital": _N, "rate": {**_N, "description": "手续费率，默认0.0001"},
             "slippage": _N, "size": {**_N, "description": "合约乘数"},
             "pricetick": _N, "setting": {**_D, "description": "策略参数"}},
            ["class_name", "vt_symbol", "start"]),
        "readonly": False,
    },
    {
        "name": "download_backtest_data",
        "description": "从网关下载历史K线入库（SIM 网关生成确定性模拟数据，STOCK 网关拉真实A股日线）。",
        "input_schema": _obj(
            {"vt_symbol": _S,
             "start": {**_S, "description": "如 2026-07-01T09:00:00"},
             "end": _S,
             "interval": {**_S, "enum": ["1m", "1h", "d"]},
             "gateway_name": {**_S, "enum": ["SIM", "STOCK"], "description": "默认SIM"}},
            ["vt_symbol", "start"]),
        "readonly": False,
    },
    {
        "name": "get_risk_settings",
        "description": "查看风控参数与运行状态（限额/熔断标志/计数器）。",
        "input_schema": _obj({}),
        "readonly": True,
    },
    {
        "name": "update_risk_settings",
        "description": "修改风控参数（如 order_size_limit/position_limit/daily_loss_limit_pct）。",
        "input_schema": _obj(
            {"updates": {**_D, "description": "要修改的参数键值对"}},
            ["updates"]),
        "readonly": False,
    },
]


def execute_tool(tools: TradingTools, name: str, arguments: dict) -> str:
    """分发一次工具调用；错误会转为 LLM 可读的文本，绝不抛出异常。"""
    method = getattr(tools, name, None)
    spec_names = {s["name"] for s in TOOL_SPECS}
    if name not in spec_names or method is None:
        return f"错误: 未知工具 {name!r}"
    try:
        result = method(**arguments)
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    except ToolExecutionError as e:
        return f"错误: {e}"
    except TypeError as e:
        return f"错误: 参数不正确 - {e}"
    except httpx.HTTPError as e:
        return f"错误: 无法连接交易系统 API - {e}"
    except Exception as e:  # noqa: BLE001 — LLM 必须始终得到回复
        return f"错误: {type(e).__name__}: {e}"
