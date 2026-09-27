/** 顶部导航栏（玻璃态）：Logo、账户概要、Gateway 状态、WebSocket 连接、
 *  MCP 配置入口、主题切换。 */

import { useEffect, useState } from 'react'
import { Badge, Button, Space, Switch, Typography } from 'antd'
import { ApiOutlined, MoonOutlined, SunOutlined } from '@ant-design/icons'
import { getHealth } from '../api/http'
import { useWsStore } from '../api/ws'
import { useThemeStore } from '../stores/theme'
import { useTradingStore } from '../stores/trading'
import McpConfigModal from './McpConfigModal'

const { Text } = Typography

export default function HeaderBar() {
  const mode = useThemeStore(s => s.mode)
  const toggle = useThemeStore(s => s.toggle)
  const wsConnected = useWsStore(s => s.connected)
  const accounts = useTradingStore(s => s.accounts)
  const [gateways, setGateways] = useState<Record<string, boolean>>({})
  const [mcpOpen, setMcpOpen] = useState(false)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const health = await getHealth()
        if (active) setGateways(health.gateways)
      } catch {
        if (active) setGateways({})
      }
    }
    void poll()
    const timer = setInterval(poll, 5000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const accountList = Object.values(accounts)
  const totalBalance = accountList.reduce((sum, a) => sum + a.balance, 0)
  const totalAvailable = accountList.reduce((sum, a) => sum + a.available, 0)

  return (
    <div className="relative z-10 flex items-center justify-between border-b border-white/80 bg-white/60 px-4 py-2 backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.06]">
      <Space size="large">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-xl text-sm font-bold text-white"
            style={{
              background: 'linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%)',
              boxShadow: '0 4px 14px rgba(139, 92, 246, 0.35)',
            }}
          >
            Q
          </div>
          <Text strong style={{ fontSize: 16 }} className="text-slate-800 dark:text-slate-100">
            Quant Trader
          </Text>
        </div>

        <Space size="small">
          <Text type="secondary" className="text-xs">权益</Text>
          <Text strong className="mono text-slate-800 dark:text-slate-100">
            {totalBalance.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
          </Text>
          <Text type="secondary" className="text-xs">可用</Text>
          <Text strong className="mono text-slate-800 dark:text-slate-100">
            {totalAvailable.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
          </Text>
        </Space>
      </Space>

      <Space size="middle">
        <Button
          icon={<ApiOutlined />}
          size="small"
          className="!rounded-xl"
          onClick={() => setMcpOpen(true)}
        >
          MCP 配置
        </Button>
        {/* Gateway 状态：半透明胶囊标签 */}
        <Space size={4}>
          {Object.entries(gateways).map(([name, connected]) => (
            <span
              key={name}
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
                connected
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300'
                  : 'bg-slate-500/10 text-slate-400'
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  connected ? 'bg-emerald-500' : 'bg-slate-400'
                }`}
              />
              {name}
            </span>
          ))}
        </Space>
        <Badge
          status={wsConnected ? 'success' : 'error'}
          text={
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {wsConnected ? '行情已连接' : '行情断开'}
            </span>
          }
        />
        <Switch
          checked={mode === 'dark'}
          onChange={toggle}
          checkedChildren={<MoonOutlined />}
          unCheckedChildren={<SunOutlined />}
        />
      </Space>

      <McpConfigModal open={mcpOpen} onClose={() => setMcpOpen(false)} />
    </div>
  )
}
