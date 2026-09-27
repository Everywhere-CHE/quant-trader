# QuantTrader 前端

QuantTrader 量化交易平台的 React 前端，与 FastAPI 后端分离部署。

## 技术栈

- **React 19** + **TypeScript** + **Vite**
- **Ant Design v6**（UI 组件，亮/暗双主题）
- **ECharts**（K 线图、资金曲线）
- **TradingView Lightweight Charts v5**（轻量级 K 线）
- **zustand**（状态管理）
- **Oxc**（lint）

## 目录结构

```
frontend/
├── src/
│   ├── components/          # 页面组件
│   │   ├── TradingPage.tsx      # 交易终端（K线/盘口/下单/底部面板）
│   │   ├── KlineChart.tsx       # K 线图
│   │   ├── OrderPanel.tsx       # 下单面板
│   │   ├── MarketList.tsx       # 自选列表
│   │   ├── BottomTabs.tsx       # 底部标签页（委托/成交/持仓/资金/日志）
│   │   ├── StrategyPage.tsx     # 策略管理
│   │   ├── BacktestPage.tsx     # 回测
│   │   ├── AIChatPage.tsx       # AI 助手
│   │   └── SettingsPage.tsx     # 设置
│   ├── stores/              # zustand 状态（market/trading/strategy/ai/theme/sound）
│   ├── api/                 # http.ts / ws.ts（REST + WebSocket）
│   └── utils/               # 工具（sound.ts 提示音等）
├── index.html
└── vite.config.ts
```

## 开发

需先启动后端（`backend/`，端口 8000）：

```bash
npm install
npm run dev        # 开发服务器 http://localhost:5173（已配置 /api、/ws 代理到 8000）
```

## 构建

```bash
npm run build      # 生产构建到 dist/（供后端打包或静态托管）
```

## WebSocket 连接

前端通过单条 WebSocket 连接（`/ws`）接收实时行情、委托、成交、持仓、资金、日志推送，并分发到各 zustand store。带退避自动重连；WebSocket 断开时启用 3 秒兜底轮询。

## 关键说明

- **登录认证**：访问页面先显示登录页（`LoginPage.tsx`），登录后获得 JWT Token 存于 localStorage，axios 拦截器自动附加到请求头；401 时自动跳转登录页。设置页可修改密码、退出登录。
- **BottomTabs 已优化**：拆分为独立子组件，各 Tab 单独订阅 store，避免行情刷新导致整个底部面板重渲染。委托/成交 tab 的"清除历史"按钮在 tab 栏右侧，标签显示实时计数。
- **持仓清仓**：持仓页"清仓"按钮用市场买卖价（`bid_price_1`/`ask_price_1`）平仓，与交易栏一键清仓一致，避免无效价格被 CTP 拒绝。
- **策略自动启动**：策略页"自动启动"开关，开启后项目重启自动 init + start 该策略。
- **回测收益率**：顶部"近期交易统计"卡显示收益率（总盈亏/账户权益）。
- **行情订阅**：不要在组件里用 `useMarketStore(s => s.ticks)` 订阅行情（会频繁重渲染），只在需要时用 `useMarketStore.getState().ticks` 取值。
- **主题**：亮/暗双主题，右上角开关切换，localStorage 记忆。