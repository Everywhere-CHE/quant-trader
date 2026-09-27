"""策略1：连续小阳/小阴线反转（优化版，自包含）。

相对原版的关键改进：
1. 消除未来函数：开仓信号整体 shift(1)，次日开盘价执行；止损/止盈价
   用前一日 ATR 计算（盘中已知），不再偷看当日收盘数据。
2. ATR 自适应阈值：小阳/小阴线的幅度阈值改用 ATR 倍数，自动适配不同
   波动率品种，替代原版写死的固定百分比。
3. 宽松连续条件：N 根中有 M 根满足即可，不再要求全部满足，缓解原版
   信号过少的问题。
4. 完整出场体系：新增固定止损 / 止盈 / 移动止损 / 时间止损四重出场，
   原版只有开仓信号、没有平仓逻辑。
5. 多空信号互斥：同一天同时满足多空条件时不交易，避免对冲歧义。

回测口径：
- 开仓：t 日收盘生成信号，t+1 日开盘价成交。
- 止损 / 止盈：t+1 日及之后，盘中触及止损/止盈价则按该价成交。
- 移动止损 / 时间止损：按收盘价判断与成交。

返回值：(signals_df, trades_df) 元组。
- signals_df：含 position / entry_price / exit_price 三列。
- trades_df：每笔交易一行，含方向、开平价、盈亏百分比、持仓根数、出场原因。
"""

import numpy as np
import pandas as pd


# ======================================================================
# 辅助函数
# ======================================================================

def _calc_atr(high, low, close, period=14):
    """ATR（Wilder 平滑）。high/low/close 可为 pd.Series 或 array-like。"""
    if hasattr(high, "iloc"):
        idx = high.index
        high = high.to_numpy(dtype=float)
        low = low.to_numpy(dtype=float)
        close = close.to_numpy(dtype=float)
    else:
        idx = None
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)

    n = len(close)
    tr = np.full(n, np.nan)
    if n > 0:
        tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    atr = np.full(n, np.nan)
    if n >= period:
        atr[period - 1] = tr[:period].mean()
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return pd.Series(atr, index=idx)


def _ema(arr, period):
    """EMA，前 period 个值用 SMA 初始化（与 talib 约定一致）。"""
    arr = np.asarray(arr, dtype=float)
    n = len(arr)
    out = np.full(n, np.nan)
    if period <= 0 or period > n:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, n):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _shift_bool(arr):
    """布尔序列向后移一位，首位置 False（无未来函数）。

    输入可为 bool/object ndarray 或 bool Series，NaN/NA 一律视为 False。
    """
    arr = np.asarray(arr)
    if arr.dtype != bool:
        arr = np.asarray(arr, dtype=bool)
    out = np.zeros(len(arr), dtype=bool)
    if len(arr) > 1:
        out[1:] = arr[:-1]
    return out


def _simulate(df, long_entry, short_entry, atr,
              stop_loss_atr, take_profit_atr,
              trailing_stop_atr, max_hold_bars):
    """通用持仓状态机。

    开仓：信号次日开盘价成交。
    止损/止盈：盘中触及则按触发价成交（止损价基于前一日 ATR）。
    移动止损 / 时间止损：按收盘价判断与成交。

    Returns:
        (signals_df, trades_df)
    """
    opn = df["open"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    # 前一日 ATR：盘中即可确定当日止损价，避免未来函数
    atr_prev = atr.shift(1).to_numpy(dtype=float)
    long_arr = np.asarray(long_entry, dtype=bool)
    short_arr = np.asarray(short_entry, dtype=bool)
    n = len(df)

    position = np.zeros(n, dtype=int)
    entry_price = np.full(n, np.nan)
    exit_price = np.full(n, np.nan)
    trades = []

    pos = 0
    ep = 0.0
    hp = 0.0      # 持仓期间最高价（多头）/ 最低价（空头）
    lp = 0.0
    held = 0
    entry_bar = -1

    for i in range(n):
        if pos == 0:
            # ---- 无持仓：检查开仓 ----
            if long_arr[i] and not np.isnan(atr_prev[i]):
                pos = 1
                ep = opn[i]
                hp = lp = opn[i]
                held = 0
                entry_bar = i
                entry_price[i] = ep
            elif short_arr[i] and not np.isnan(atr_prev[i]):
                pos = -1
                ep = opn[i]
                hp = lp = opn[i]
                held = 0
                entry_bar = i
                entry_price[i] = ep
        else:
            # ---- 持仓：检查出场 ----
            held += 1
            a = atr_prev[i]
            if pos > 0:
                hp = max(hp, high[i])
            else:
                lp = min(lp, low[i])

            exit_flag = False
            exit_px = np.nan
            reason = ""

            # 1) 固定止损（盘中触及止损价）
            if stop_loss_atr > 0 and not np.isnan(a):
                if pos > 0:
                    sl = ep - stop_loss_atr * a
                    if low[i] <= sl:
                        exit_flag, exit_px, reason = True, sl, "stop_loss"
                else:
                    sl = ep + stop_loss_atr * a
                    if high[i] >= sl:
                        exit_flag, exit_px, reason = True, sl, "stop_loss"

            # 2) 止盈（盘中触及止盈价）
            if not exit_flag and take_profit_atr > 0 and not np.isnan(a):
                if pos > 0:
                    tp = ep + take_profit_atr * a
                    if high[i] >= tp:
                        exit_flag, exit_px, reason = True, tp, "take_profit"
                else:
                    tp = ep - take_profit_atr * a
                    if low[i] <= tp:
                        exit_flag, exit_px, reason = True, tp, "take_profit"

            # 3) 移动止损（从极值回撤 N 倍 ATR，收盘价判断）
            if not exit_flag and trailing_stop_atr > 0 and not np.isnan(a):
                if pos > 0 and hp > 0:
                    if (hp - close[i]) >= trailing_stop_atr * a:
                        exit_flag, exit_px, reason = True, close[i], "trailing_stop"
                elif pos < 0 and lp > 0:
                    if (close[i] - lp) >= trailing_stop_atr * a:
                        exit_flag, exit_px, reason = True, close[i], "trailing_stop"

            # 4) 时间止损（持仓满 max_hold_bars 根 K 线）
            if not exit_flag and max_hold_bars > 0 and held >= max_hold_bars:
                exit_flag, exit_px, reason = True, close[i], "time_stop"

            if exit_flag:
                exit_price[i] = exit_px
                trades.append({
                    "entry_bar": entry_bar,
                    "exit_bar": i,
                    "direction": pos,
                    "entry_price": ep,
                    "exit_price": exit_px,
                    "pnl_pct": (exit_px - ep) / ep * pos * 100,
                    "bars_held": held,
                    "reason": reason,
                })
                pos = 0
                ep = hp = lp = 0.0
                held = 0
                entry_bar = -1

        position[i] = pos

    out = df.copy()
    out["position"] = position
    out["entry_price"] = entry_price
    out["exit_price"] = exit_price
    return out[["position", "entry_price", "exit_price"]], pd.DataFrame(trades)


# ======================================================================
# 策略1：连续小阳/小阴线反转
# ======================================================================

def strategy1_continuous_move(
    df,
    down_lookback=20,         # 做多前：下跌回看天数
    down_return=-0.08,        # 做多前：累计跌幅阈值（-8%）
    up_lookback=20,           # 做空前：上涨回看天数
    up_return=0.08,           # 做空前：累计涨幅阈值（+8%）
    consec_days=3,            # 连续K线判定窗口
    min_consec=2,             # 窗口中至少满足的根数（放宽，避免信号过少）
    atr_mult_min=0.3,         # 小阳/小阴线最小幅度 = N 倍 ATR
    atr_mult_max=1.2,         # 小阳/小阴线最大幅度 = N 倍 ATR
    atr_window=14,            # ATR 计算周期
    stop_loss_atr=2.0,        # 固定止损（ATR 倍数，0=关闭）
    take_profit_atr=4.0,      # 止盈（ATR 倍数，0=关闭）
    trailing_stop_atr=1.5,    # 移动止损（ATR 倍数，0=关闭）
    max_hold_bars=30,         # 时间止损（K线根数，0=关闭）
):
    """
    策略1（优化版）：连续小阳/小阴线反转。

    - 做多：前期累计跌幅超过 down_return → 最近 consec_days 根中至少
      min_consec 根是小阳线（涨幅在 atr_mult_min~atr_mult_max 倍 ATR 之间）→ 开多
    - 做空：前期累计涨幅超过 up_return → 最近 consec_days 根中至少
      min_consec 根是小阴线 → 开空

    Returns:
        (signals_df, trades_df)
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]

    atr = _calc_atr(high, low, close, atr_window)
    pct = close.pct_change()

    # 动态阈值：ATR 转成价格百分比，shift(1) 用前一日 ATR
    atr_pct = (atr / close).shift(1)
    lo = atr_mult_min * atr_pct
    hi = atr_mult_max * atr_pct

    # 小阳线 / 小阴线
    up_day = (pct >= lo) & (pct <= hi) & (pct > 0)
    down_day = (pct <= -lo) & (pct >= -hi) & (pct < 0)

    # 连续 N 根中至少 M 根满足
    consec_up = up_day.rolling(consec_days).sum().fillna(0) >= min_consec
    consec_down = down_day.rolling(consec_days).sum().fillna(0) >= min_consec

    # 前期涨跌
    past_ret_down = close / close.shift(down_lookback) - 1
    past_ret_up = close / close.shift(up_lookback) - 1

    long_cond = (past_ret_down <= down_return) & consec_up
    short_cond = (past_ret_up >= up_return) & consec_down

    # 多空互斥：同时触发则不交易。shift(1) 后首行视为 False。
    both = long_cond & short_cond
    long_entry = pd.Series(_shift_bool((long_cond & ~both).to_numpy()), index=df.index)
    short_entry = pd.Series(_shift_bool((short_cond & ~both).to_numpy()), index=df.index)

    return _simulate(
        df, long_entry, short_entry, atr,
        stop_loss_atr, take_profit_atr,
        trailing_stop_atr, max_hold_bars,
    )


# ======================================================================
# 自测 demo
# ======================================================================

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from datetime import datetime, timedelta

    # 构造含"下跌→连续小阳反弹"和"上涨→连续小阴下跌"的模拟日K
    rng = np.random.default_rng(42)
    n = 600
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]

    close = np.zeros(n)
    close[0] = 100.0
    for i in range(1, n):
        if i < 120:          # 下跌段
            r = rng.normal(-0.003, 0.015)
        elif i < 150:        # 连续小阳反弹
            r = rng.normal(0.009, 0.004)
        elif i < 300:        # 震荡上行
            r = rng.normal(0.0015, 0.012)
        elif i < 330:        # 连续小阴下跌
            r = rng.normal(-0.009, 0.004)
        else:                # 震荡
            r = rng.normal(0.001, 0.013)
        close[i] = close[i - 1] * (1 + r)

    opn = close * (1 + rng.normal(0, 0.004, n))
    high = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol = rng.integers(1000, 5000, n).astype(float)

    df = pd.DataFrame({
        "datetime": dates, "open": opn, "high": high,
        "low": low, "close": close, "volume": vol,
    })

    print("=" * 60)
    print("策略1：连续小阳/小阴线反转")
    print("=" * 60)
    sig1, trades1 = strategy1_continuous_move(df)
    print(f"数据 {n} 根，价格区间 {close.min():.2f} ~ {close.max():.2f}")
    print(f"交易笔数: {len(trades1)}")
    if len(trades1) > 0:
        wins = (trades1["pnl_pct"] > 0).sum()
        print(f"胜率: {wins}/{len(trades1)} = {wins/len(trades1)*100:.1f}%")
        print(f"平均每笔盈亏: {trades1['pnl_pct'].mean():.2f}%")
        print(f"总盈亏(求和): {trades1['pnl_pct'].sum():.2f}%")
        print("\n出场原因分布:")
        print(trades1["reason"].value_counts().to_string())
        print("\n前5笔交易:")
        print(trades1.head().to_string(index=False))
