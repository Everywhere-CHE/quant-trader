"""用户自选列表：持久化保存在行情面板中显示的 vt_symbol 列表。
用户可以添加任何关心的合约 — 任意 Gateway 中的已知合约，
或任意 A 股代码（ STOCK Gateway 在订阅时会惰性注册
未知代码）。"""

import json
from pathlib import Path

from .config import DATA_DIR

CONFIG_PATH = DATA_DIR / "watchlist.json"

# 首次运行时的默认自选列表：仅包含真实 A 股代码（由 STOCK
# Gateway 惰性注册；名称来自实时行情推送）。
# 期货合约在 CTP 连接后出现，之后即可添加。
DEFAULT_WATCHLIST = [
    "600519.SSE",
    "601318.SSE",
    "510300.SSE",
    "000001.SZSE",
    "300750.SZSE",
]


def load_watchlist() -> list[str]:
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(s) for s in data]
    except Exception:
        pass
    return list(DEFAULT_WATCHLIST)


def save_watchlist(symbols: list[str]) -> list[str]:
    # 去重并保持原有顺序
    seen: set[str] = set()
    cleaned: list[str] = []
    for symbol in symbols:
        s = str(symbol).strip()
        if s and s not in seen:
            seen.add(s)
            cleaned.append(s)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cleaned


def add_symbol(vt_symbol: str) -> list[str]:
    symbols = load_watchlist()
    if vt_symbol not in symbols:
        symbols.append(vt_symbol)
    return save_watchlist(symbols)


def remove_symbol(vt_symbol: str) -> list[str]:
    symbols = [s for s in load_watchlist() if s != vt_symbol]
    return save_watchlist(symbols)
