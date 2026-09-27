/** Axios 客户端与 REST 接口封装。 */

import axios from 'axios'
import type {
  Account,
  BacktestTask,
  Bar,
  Contract,
  GatewayInfo,
  HealthInfo,
  LogEntry,
  Order,
  Position,
  StrategyClassInfo,
  StrategyData,
  Tick,
  Trade,
} from '../types'

export const http = axios.create({ baseURL: '/api', timeout: 60000 })

// 401 重定向去重标记（防止并发 401 触发多次重载）
let isRedirecting = false

// 请求拦截器：自动附加 Authorization 头
http.interceptors.request.use(config => {
  const token = localStorage.getItem('auth_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 时清除 token 并跳转登录页
http.interceptors.response.use(
  res => res,
  error => {
    if (error.response?.status === 401 && !isRedirecting) {
      isRedirecting = true
      localStorage.removeItem('auth_token')
      // 重载当前页触发重新鉴权：auth gate 检测到无 token 后渲染
      // LoginPage。修复原先跳 /login 的 hack（生产 StaticFiles 下
      // /login 这类路径会 404）；HashRouter 下重载会保留 hash 路由，
      // 重新登录后可回到原页面。
      window.location.reload()
    }
    return Promise.reject(error)
  },
)

// ----- 系统 -----
export const getHealth = () => http.get<HealthInfo>('/health').then(r => r.data)
export const getLogs = (limit = 200) =>
  http.get<LogEntry[]>('/logs', { params: { limit } }).then(r => r.data)

// ----- Gateway 接口 -----
export const getGateways = () =>
  http.get<GatewayInfo[]>('/gateways').then(r => r.data)
export const connectGateway = (name: string, setting: Record<string, unknown> = {}) =>
  http.post(`/gateways/${name}/connect`, { setting }).then(r => r.data)
export const disconnectGateway = (name: string) =>
  http.post(`/gateways/${name}/disconnect`).then(r => r.data)
export const subscribeSymbols = (gateway: string, vtSymbols: string[]) =>
  http.post(`/gateways/${gateway}/subscribe`, { vt_symbols: vtSymbols }).then(r => r.data)

// ----- CTP 账户配置 -----
export interface CtpConfig {
  userid: string
  password: string
  has_password: boolean
  brokerid: string
  td_address: string
  md_address: string
  appid: string
  auth_code: string
}
export interface CtpServerPreset {
  id: string
  label: string
  note: string
  brokerid: string
  td_address: string
  md_address: string
  appid: string
  auth_code: string
}
export const getCtpConfig = () =>
  http.get<CtpConfig>('/gateways/ctp/config').then(r => r.data)
export const getCtpPresets = () =>
  http.get<CtpServerPreset[]>('/gateways/ctp/presets').then(r => r.data)
export const updateCtpConfig = (config: Partial<Record<keyof CtpConfig, string>>) =>
  http.put<CtpConfig>('/gateways/ctp/config', config).then(r => r.data)

// ----- STOCK 股票 Gateway 配置 -----
export interface StockConfig {
  poll_interval: number
}
export const getStockConfig = () =>
  http.get<StockConfig>('/gateways/stock/config').then(r => r.data)
export const updateStockConfig = (config: Partial<StockConfig>) =>
  http.put<StockConfig>('/gateways/stock/config', config).then(r => r.data)

// ----- 行情 -----
export const getContracts = (keyword = '', limit = 0, futures = false) =>
  http
    .get<Contract[]>('/contracts', {
      params: {
        keyword: keyword || undefined,
        limit: limit || undefined,
        futures: futures || undefined,
      },
    })
    .then(r => r.data)
export const getTicks = () => http.get<Tick[]>('/ticks').then(r => r.data)
export const getWatchlist = () =>
  http.get<{ symbols: string[] }>('/watchlist').then(r => r.data.symbols)
export const addWatchSymbol = (vtSymbol: string) =>
  http
    .post<{ symbols: string[] }>('/watchlist', { vt_symbol: vtSymbol })
    .then(r => r.data.symbols)
export const removeWatchSymbol = (vtSymbol: string) =>
  http
    .delete<{ symbols: string[] }>(`/watchlist/${vtSymbol}`)
    .then(r => r.data.symbols)
export const getBars = (
  vtSymbol: string,
  interval: string,
  fromGateway = false,
) =>
  http
    .get<Bar[]>('/bars', {
      params: { vt_symbol: vtSymbol, interval, from_gateway: fromGateway },
    })
    .then(r => r.data)
export const getIntradayBars = (vtSymbol: string, interval = '1m', limit = 500) =>
  http
    .get<Bar[]>('/bars/intraday', {
      params: { vt_symbol: vtSymbol, interval, limit },
    })
    .then(r => r.data)

// ----- 交易 -----
export interface PlaceOrderReq {
  vt_symbol: string
  direction: string
  offset: string
  type: string
  price: number
  volume: number
}
export const placeOrder = (req: PlaceOrderReq) =>
  http.post<{ vt_orderid: string }>('/orders', req).then(r => r.data)
export const cancelOrder = (vtOrderid: string) =>
  http.delete(`/orders/${vtOrderid}`).then(r => r.data)
export const getOrders = () => http.get<Order[]>('/orders').then(r => r.data)
export const getTrades = () => http.get<Trade[]>('/trades').then(r => r.data)
export const getPositions = () =>
  http.get<Position[]>('/positions').then(r => r.data)
export const getAccounts = () =>
  http.get<Account[]>('/accounts').then(r => r.data)

// ----- 委托/成交历史管理 -----
export const deleteOrderHistory = (vtOrderid: string) =>
  http.delete(`/orders/${vtOrderid}/history`).then(r => r.data)
export const clearOrderHistory = () =>
  http.delete('/history/orders').then(r => r.data)
export const clearTradeHistory = () =>
  http.delete('/history/trades').then(r => r.data)

// ----- 策略 -----
export const getStrategies = () =>
  http.get<StrategyData[]>('/strategies').then(r => r.data)
export const getStrategyClasses = () =>
  http.get<StrategyClassInfo[]>('/strategies/classes').then(r => r.data)
export const createStrategy = (body: {
  class_name: string
  name: string
  vt_symbol?: string
  vt_symbols?: string[]
  setting: Record<string, unknown>
}) => http.post('/strategies', body).then(r => r.data)
export const editStrategy = (name: string, setting: Record<string, unknown>) =>
  http.put(`/strategies/${name}`, { setting }).then(r => r.data)
export const deleteStrategy = (name: string) =>
  http.delete(`/strategies/${name}`).then(r => r.data)
export const initStrategy = (name: string) =>
  http.post(`/strategies/${name}/init`).then(r => r.data)
export const startStrategy = (name: string) =>
  http.post(`/strategies/${name}/start`).then(r => r.data)
export const stopStrategy = (name: string) =>
  http.post(`/strategies/${name}/stop`).then(r => r.data)
export const setAutoStart = (name: string, enabled: boolean) =>
  http.put(`/strategies/${name}/auto-start`, { enabled }).then(r => r.data)

// ----- 持仓对账 -----
export interface ReconcileRow {
  strategy_name: string
  vt_symbol: string
  strategy_pos: number
  gateway_net_pos: number
  diff: number
  matched: boolean
  shared: boolean
  gateway_has_position: boolean
  trading: boolean
}
export const reconcilePositions = () =>
  http.get<ReconcileRow[]>('/strategies/reconcile').then(r => r.data)
export const syncStrategyPos = (name: string, pos?: number) =>
  http
    .post<{ strategy_name: string; old_pos: number; new_pos: number; mode?: string }>(
      `/strategies/${name}/sync-pos${pos !== undefined ? `?pos=${pos}` : ''}`,
    )
    .then(r => r.data)
export const getStrategyFiles = () =>
  http
    .get<{ filename: string; size: number; modified: number }[]>(
      '/strategies/files',
    )
    .then(r => r.data)
export const readStrategyFile = (filename: string) =>
  http
    .get<{ filename: string; code: string }>(`/strategies/files/${filename}`)
    .then(r => r.data)
export const writeStrategyFile = (
  filename: string,
  code: string,
  overwrite = false,
) =>
  http
    .post<{
      saved: string
      classes_found: string[]
      total_classes: number
    }>('/strategies/files', { filename, code, overwrite })
    .then(r => r.data)

// ----- 回测 -----
export interface PerformanceResult {
  hours: number
  since: string
  now: string
  total_trades: number
  win_count: number
  loss_count: number
  win_rate: number
  total_return: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  total_fee: number
  symbols: string[]
  trades: { vt_symbol: string; direction: string; price: number; volume: number; pnl: number; datetime: string | null }[]
  positions: { vt_symbol: string; direction: string; volume: number; price: number; pnl: number }[]
}
export const getPerformance = (hours: number) =>
  http.get<PerformanceResult>('/backtest/performance', { params: { hours } }).then(r => r.data)
export interface BacktestReq {
  class_name?: string
  class_names?: string[]
  vt_symbol?: string
  vt_symbols?: string[]
  interval: string
  start: string
  end?: string
  capital: number
  rate: number
  slippage: number
  size: number
  pricetick: number
  setting: Record<string, unknown>
}
export const runBacktest = (body: BacktestReq) =>
  http.post<BacktestTask>('/backtest', body).then(r => r.data)
export const getBacktestTask = (taskId: string) =>
  http.get<BacktestTask>(`/backtest/${taskId}`).then(r => r.data)
export const listBacktestTasks = () =>
  http.get<{ tasks: BacktestTask[] }>('/backtest').then(r => r.data)
export const downloadBacktestData = (body: {
  vt_symbol: string
  interval: string
  start: string
  end?: string
  gateway_name?: string
}) => http.post('/backtest/download-data', body).then(r => r.data)
export const getBacktestDataOverview = (vtSymbol: string, interval: string) =>
  http
    .get('/backtest/data', { params: { vt_symbol: vtSymbol, interval } })
    .then(r => r.data)

// ----- 风控 -----
export const getRisk = () =>
  http
    .get<{ settings: Record<string, number | boolean>; status: Record<string, unknown> }>(
      '/risk',
    )
    .then(r => r.data)
export const updateRisk = (settings: Record<string, number | boolean>) =>
  http.put('/risk', settings).then(r => r.data)
export const setTrailingStop = (key: string, pct: number) =>
  http.put('/risk/trailing-stop', { key, pct }).then(r => r.data)
export const removeTrailingStop = (key: string) =>
  http.delete(`/risk/trailing-stop/${encodeURIComponent(key)}`).then(r => r.data)

// ----- AI 助手 -----
export interface AiStatus {
  enabled: boolean
  provider: string
  model: string
  base_url: string
  has_api_key: boolean
  allow_trading: boolean
  auto_optimize: boolean
}
export interface AiPreset {
  id: string
  group: string
  label: string
  provider: string
  model: string
  base_url: string
}
export interface AiToolCall {
  name: string
  input: Record<string, unknown>
  output: string
}
export interface AiChatResponse {
  reply: string
  tool_calls: AiToolCall[]
  messages: unknown[]
}
export const getAiStatus = () =>
  http.get<AiStatus>('/ai/status').then(r => r.data)
export const getAiPresets = () =>
  http.get<AiPreset[]>('/ai/presets').then(r => r.data)
export const updateAiConfig = (config: {
  provider?: string
  model?: string
  base_url?: string
  api_key?: string
  allow_trading?: boolean
  auto_optimize?: boolean
}) => http.put<AiStatus>('/ai/config', config).then(r => r.data)
export const postAiChat = (
  messages: unknown[],
  conversationId?: string,
  displayMessages?: { role: string; text: string }[],
) =>
  http
    .post<AiChatResponse>(
      '/ai/chat',
      {
        messages,
        conversation_id: conversationId,
        display_messages: displayMessages,
      },
      { timeout: 600000 },
    )
    .then(r => r.data)

// ----- AI 会话管理 -----
export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}
export interface Conversation extends ConversationSummary {
  messages: unknown[]
  display_messages: { role: string; text: string }[]
}
export const listConversations = () =>
  http.get<ConversationSummary[]>('/conversations').then(r => r.data)
export const getConversation = (id: string) =>
  http.get<Conversation>(`/conversations/${id}`).then(r => r.data)
export const createConversation = () =>
  http.post<Conversation>('/conversations').then(r => r.data)
export const deleteConversation = (id: string) =>
  http.delete(`/conversations/${id}`).then(r => r.data)
export const reloadStrategies = () =>
  http.post('/strategies/reload').then(r => r.data)

// ----- MCP 配置 -----
export const getMcpToken = () =>
  http.get<{ token: string }>('/auth/mcp-token').then(r => r.data)
export const refreshMcpToken = () =>
  http.post<{ token: string }>('/auth/mcp-token/refresh').then(r => r.data)
/** 下载预置了服务器地址与 MCP Token 的专属客户端脚本。 */
export const downloadMcpScript = async (baseUrl?: string) => {
  const resp = await http.get('/mcp/script', {
    params: baseUrl ? { base: baseUrl } : undefined,
    responseType: 'blob',
  })
  const blob = new Blob([resp.data as BlobPart], { type: 'text/x-python' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'quant_trader_mcp.py'
  a.click()
  URL.revokeObjectURL(url)
}
