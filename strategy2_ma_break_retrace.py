"""策略2：均线突破 + 黄金分割回调（优化版，自包含）。

相对原版的关键改进：
1. 消除未来函数：开仓信号整体 shift(1)，次日开盘价执行；止损/止盈价
   用前一日 ATR 计算（盘中已知）。
2. 黄金分割位改用 K 线实体（开盘→收盘）计算，而非当日最高/最低——
   原版用当日 high/low 算回调位，但当日高低点收盘才确定，构成未来函数。
3. 突破需超过均线一定幅度（breakout_pct），过滤贴着均线走的假突破。
4. 回调确认要求收盘价站稳在回调位之上/之下，而非盘中针尖触碰即确认。
5. 大阳/大阴线用收盘涨幅（ATR 倍数）判定，适配不同波动率品种。
6. 完整出场体系：固定止损 / 止盈 / 移动止损 / 时间止损。
7. 多空信号互斥：同日同时触发不交易。

回测口径：
- 开仓：t 日收盘生成信号，t+1 日开盘价成交。
- 止损 / 止盈：盘中触及则按该价成交。
- 移动止损 / 时间止损：按收盘价判断与成交。

返回值：(signals_df, trades_df) 元组。
- signals_df：含 position / entry_price / exit_price 三列。
- trades_df：每笔交易一行，含方向、开平价、盈亏百分比、持仓根数、出场原因。

注意：策略2 的触发条件较严格（突破 + 大阳 + 前期趋势 + 回调到位 + 确认），
信号频率天然较低。demo 用专门构造的"深跌→大阳突破→回调"行情验证逻辑
能跑通；真实品种上需根据波动率调整 trend_return / big_candle_atr /
breakout_pct 等参数。
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
# 策略2：均线突破 + 黄金分割回调
# ======================================================================

def strategy2_ma_break_retrace(
    df,
    ma_fast=30,               # 快均线周期（0=不使用）
    ma_slow=60,               # 慢均线周期（0=不使用）
    breakout_pct=0.005,       # 突破需超过均线的幅度（0.5%），过滤假突破
    trend_lookback=21,        # 趋势回看天数（以突破前一日为基准，不含突破当日）
    trend_return=0.08,        # 趋势阈值（±8%）
    big_candle_atr=1.5,       # 大阳/大阴线：收盘涨幅 >= N 倍 ATR（百分比）
    atr_window=14,            # ATR 计算周期
    fib_levels=(0.382, 0.5, 0.618),  # 黄金分割回调位
    require_confirm=True,     # 回调位是否需要收盘站稳确认
    max_wait=10,              # 触发后最多等待 K线根数
    stop_loss_atr=2.0,        # 固定止损（ATR 倍数，0=关闭）
    take_profit_atr=4.0,      # 止盈（ATR 倍数，0=关闭）
    trailing_stop_atr=1.5,    # 移动止损（ATR 倍数，0=关闭）
    max_hold_bars=40,         # 时间止损（K线根数，0=关闭）
):
    """
    策略2（优化版）：均线突破 + 黄金分割回调。

    - 做多：前期下跌 → 突破均线（超过 breakout_pct 幅度）+ 大阳线（收盘涨幅 >=
      big_candle_atr 倍 ATR）→ 等待回调至该阳线实体的黄金分割位 →
      收盘站稳确认 → 开多
    - 做空：前期上涨 → 跌破均线 + 大阴线 → 等待反弹至阴线实体黄金分割位 →
      收盘站稳确认 → 开空

    黄金分割位基于 K 线实体（开盘→收盘）计算，收盘即确定，无未来函数。

    Returns:
        (signals_df, trades_df)
    """
    df = df.copy()
    close = df["close"].to_numpy(dtype=float)
    opn = df["open"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(df)

    atr = _calc_atr(df["high"], df["low"], df["close"], atr_window)
    atr_arr = atr.to_numpy(dtype=float)

    ma_fast_arr = _ema(close, ma_fast) if ma_fast > 0 else np.full(n, np.nan)
    ma_slow_arr = _ema(close, ma_slow) if ma_slow > 0 else np.full(n, np.nan)

    # 前期趋势：以"突破前一日收盘"为基准，突破当日涨幅不参与趋势判断
    past_ret = np.full(n, np.nan)
    if trend_lookback > 0 and n > trend_lookback + 1:
        # past_ret[i] = close[i-1] / close[i-1-trend_lookback] - 1
        # i = trend_lookback+1 起有效
        past_ret[trend_lookback + 1:] = (
            close[trend_lookback:-1] / close[:n - trend_lookback - 1] - 1
        )

    long_entry = np.zeros(n, dtype=bool)
    short_entry = np.zeros(n, dtype=bool)

    pending = None  # {'direction','age','trigger_low','trigger_high','levels'}

    for i in range(n):
        # ---- 先处理等待回调的 pending ----
        if pending is not None:
            pending["age"] += 1
            if pending["age"] > max_wait:
                pending = None
            else:
                direction = pending["direction"]
                levels = pending["levels"]
                if direction == "long":
                    # 失效：跌破触发阳线最低点
                    if low[i] < pending["trigger_low"]:
                        pending = None
                    else:
                        for lvl in levels:
                            if low[i] <= lvl <= high[i]:
                                ok = (close[i] > opn[i] and close[i] >= lvl) if require_confirm else True
                                if ok:
                                    long_entry[i] = True
                                    pending = None
                                    break
                else:  # short
                    # 失效：突破触发阴线最高点
                    if high[i] > pending["trigger_high"]:
                        pending = None
                    else:
                        for lvl in levels:
                            if low[i] <= lvl <= high[i]:
                                ok = (close[i] < opn[i] and close[i] <= lvl) if require_confirm else True
                                if ok:
                                    short_entry[i] = True
                                    pending = None
                                    break

        # ---- 无 pending 且今日未成交：检查新触发 ----
        if pending is None and not long_entry[i] and not short_entry[i]:
            if i < 1 or np.isnan(atr_arr[i]) or atr_arr[i] <= 0:
                continue
            if np.isnan(past_ret[i]):
                continue

            prev_c = close[i - 1]
            curr_c = close[i]

            # 均线突破判断（需超过 breakout_pct 幅度）
            break_up = False
            break_down = False
            if ma_fast > 0 and not np.isnan(ma_fast_arr[i]):
                th = breakout_pct * ma_fast_arr[i]
                if curr_c > ma_fast_arr[i] + th and prev_c <= ma_fast_arr[i]:
                    break_up = True
                if curr_c < ma_fast_arr[i] - th and prev_c >= ma_fast_arr[i]:
                    break_down = True
            if ma_slow > 0 and not np.isnan(ma_slow_arr[i]):
                th = breakout_pct * ma_slow_arr[i]
                if curr_c > ma_slow_arr[i] + th and prev_c <= ma_slow_arr[i]:
                    break_up = True
                if curr_c < ma_slow_arr[i] - th and prev_c >= ma_slow_arr[i]:
                    break_down = True

            # 大阳/大阴线：收盘涨幅 >= big_candle_atr 倍 ATR（百分比）
            pct_ret = (curr_c - prev_c) / prev_c if prev_c > 0 else 0.0
            atr_pct = atr_arr[i] / prev_c if prev_c > 0 else 0.0
            is_big = abs(pct_ret) >= big_candle_atr * atr_pct
            is_bull = curr_c > opn[i]
            is_bear = curr_c < opn[i]

            if break_up and is_big and is_bull and past_ret[i] <= -trend_return:
                # 用实体（开盘→收盘）算黄金分割位，收盘即确定
                body_low = min(opn[i], curr_c)
                body_high = max(opn[i], curr_c)
                rng = body_high - body_low
                levels = sorted(body_high - rng * f for f in fib_levels)
                pending = {
                    "direction": "long", "age": 0,
                    "trigger_low": low[i], "trigger_high": high[i],
                    "levels": levels,
                }
            elif break_down and is_big and is_bear and past_ret[i] >= trend_return:
                body_low = min(opn[i], curr_c)
                body_high = max(opn[i], curr_c)
                rng = body_high - body_low
                levels = sorted(body_low + rng * f for f in fib_levels)
                pending = {
                    "direction": "short", "age": 0,
                    "trigger_low": low[i], "trigger_high": high[i],
                    "levels": levels,
                }

    # 信号 shift(1)：t 日收盘确认，t+1 日开盘执行
    long_entry_s = pd.Series(_shift_bool(long_entry), index=df.index)
    short_entry_s = pd.Series(_shift_bool(short_entry), index=df.index)

    return _simulate(
        df, long_entry_s, short_entry_s, atr,
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

    # 构造"深跌 → 大阳突破 → 回调 → 反弹"的模拟日K，验证策略2逻辑能触发
    # 关键：下跌段要足够长，使突破发生时 21 日趋势窗口仍为负
    rng = np.random.default_rng(7)
    n = 300
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]

    close = np.zeros(n)
    close[0] = 100.0
    for i in range(1, n):
        if i < 120:         # 长下跌段（120天，跌幅约 -40%）
            r = rng.normal(-0.004, 0.012)
        elif i < 125:       # 连续大阳突破
            r = rng.normal(0.04, 0.008)
        elif i < 140:       # 回调
            r = rng.normal(-0.01, 0.006)
        elif i < 220:       # 震荡上行
            r = rng.normal(0.002, 0.01)
        elif i < 225:       # 连续大阴跌破
            r = rng.normal(-0.04, 0.008)
        elif i < 240:       # 反弹
            r = rng.normal(0.01, 0.006)
        else:               # 震荡
            r = rng.normal(0.001, 0.012)
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
    print("策略2：均线突破 + 黄金分割回调")
    print("=" * 60)
    sig2, trades2 = strategy2_ma_break_retrace(df)
    print(f"数据 {n} 根，价格区间 {close.min():.2f} ~ {close.max():.2f}")
    print(f"交易笔数: {len(trades2)}")
    if len(trades2) > 0:
        wins = (trades2["pnl_pct"] > 0).sum()
        print(f"胜率: {wins}/{len(trades2)} = {wins/len(trades2)*100:.1f}%")
        print(f"平均每笔盈亏: {trades2['pnl_pct'].mean():.2f}%")
        print(f"总盈亏(求和): {trades2['pnl_pct'].sum():.2f}%")
        print("\n出场原因分布:")
        print(trades2["reason"].value_counts().to_string())
        print("\n全部交易:")
        print(trades2.to_string(index=False))
    else:
        print("（未触发信号，可调整 trend_return / big_candle_atr 等参数）")
