/** 领域类型定义，与后端 JSON 序列化格式保持一致。 */

export interface Tick {
  vt_symbol: string
  symbol: string
  exchange: string
  datetime: string | null
  name: string
  volume: number
  turnover: number
  open_interest: number
  last_price: number
  limit_up: number
  limit_down: number
  open_price: number
  high_price: number
  low_price: number
  pre_close: number
  gateway_name: string
  bid_price_1: number
  bid_price_2: number
  bid_price_3: number
  bid_price_4: number
  bid_price_5: number
  ask_price_1: number
  ask_price_2: number
  ask_price_3: number
  ask_price_4: number
  ask_price_5: number
  bid_volume_1: number
  bid_volume_2: number
  bid_volume_3: number
  bid_volume_4: number
  bid_volume_5: number
  ask_volume_1: number
  ask_volume_2: number
  ask_volume_3: number
  ask_volume_4: number
  ask_volume_5: number
}

export interface Order {
  vt_orderid: string
  vt_symbol: string
  symbol: string
  exchange: string
  orderid: string
  type: string
  direction: string | null
  offset: string
  price: number
  volume: number
  traded: number
  status: string
  datetime: string | null
  reference: string
  gateway_name: string
}

export interface Trade {
  vt_tradeid: string
  vt_orderid: string
  vt_symbol: string
  symbol: string
  exchange: string
  orderid: string
  tradeid: string
  direction: string | null
  offset: string
  price: number
  volume: number
  datetime: string | null
  gateway_name: string
  pnl: number
  pnl_gross: number
  fee: number
  entry_price: number
}

export interface Position {
  vt_positionid: string
  vt_symbol: string
  symbol: string
  exchange: string
  direction: string
  volume: number
  frozen: number
  price: number
  pnl: number
  yd_volume: number
  gateway_name: string
  datetime: string | null
}

export interface Account {
  vt_accountid: string
  accountid: string
  balance: number
  frozen: number
  available: number
  gateway_name: string
}

export interface Contract {
  vt_symbol: string
  symbol: string
  exchange: string
  name: string
  product: string
  size: number
  pricetick: number
  min_volume: number
  stop_supported: boolean
  net_position: boolean
  history_data: boolean
  gateway_name: string
}

export interface LogEntry {
  time: string | null
  level: number
  msg: string
  gateway_name: string
}

export interface Bar {
  vt_symbol?: string
  symbol?: string
  exchange?: string
  datetime: string | null
  interval?: string | null
  volume: number
  turnover?: number
  open_interest?: number
  open_price: number
  high_price: number
  low_price: number
  close_price: number
}

export interface GatewayInfo {
  name: string
  connected: boolean
  default_setting: Record<string, string | number | boolean>
  exchanges: string[]
}

export interface StrategyData {
  strategy_name: string
  class_name: string
  vt_symbol: string
  author: string
  parameters: Record<string, unknown>
  variables: Record<string, unknown> & {
    inited?: boolean
    trading?: boolean
    pos?: number
  }
  auto_start?: boolean
}

export interface StrategyClassInfo {
  class_name: string
  display_name?: string
  author: string
  description: string
  parameters: Record<string, unknown>
  param_descriptions: Record<string, string>
  variable_descriptions: Record<string, string>
  variables: string[]
}

export interface StrategyFileInfo {
  filename: string
  size: number
  modified: number
}

export interface StrategyLogEntry {
  strategy_name: string
  msg: string
  time: string
}

export interface BacktestStatistics {
  start_date: string
  end_date: string
  total_days: number
  profit_days: number
  loss_days: number
  capital: number
  end_balance: number
  total_return: number
  annual_return: number
  max_drawdown: number
  max_ddpercent: number
  max_drawdown_duration: number
  total_net_pnl: number
  total_commission: number
  total_slippage: number
  total_turnover: number
  total_trade_count: number
  daily_return: number
  return_std: number
  sharpe_ratio: number
  return_drawdown_ratio: number
  win_rate: number
  profit_factor: number
}

export interface DailyResult {
  date: string
  close_price: number
  pre_close: number
  trade_count: number
  start_pos: number
  end_pos: number
  turnover: number
  commission: number
  slippage: number
  trading_pnl: number
  holding_pnl: number
  total_pnl: number
  net_pnl: number
}

export interface BacktestResult {
  statistics: BacktestStatistics | BacktestStatistics[]
  daily_results: DailyResult[]
  trades: Trade[]
  logs: string[]
}

export interface BacktestTask {
  task_id: string
  status: 'pending' | 'running' | 'done' | 'failed'
  message: string
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  error: string
  result?: BacktestResult | null
}

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

export interface RiskStatus {
  active: boolean
  settings: Record<string, number | boolean>
  status: Record<string, number | boolean | string>
}

export interface HealthInfo {
  status: string
  app: string
  version: string
  engine_state: string
  gateways: Record<string, boolean>
  ws_clients: number
  event_queue_size: number
  dropped_ws_msgs: number
}

/** WebSocket 消息信封。 */
export interface WsMessage {
  type: string
  data: Record<string, unknown>
}
