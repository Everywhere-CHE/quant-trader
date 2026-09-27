import { Suspense, lazy, useEffect, useState } from 'react'
import { ConfigProvider, Spin, Tabs, notification, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useLocation, useNavigate } from 'react-router-dom'
import { setNotifier } from './api/notifier'
import { wsClient } from './api/ws'
import HeaderBar from './components/HeaderBar'
import AuroraBackground from './components/ui/AuroraBackground'
import LoginPage from './components/LoginPage'
import TradingPage from './components/TradingPage'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

// 非交易页面采用懒加载，以保持初始分包体积较小
//（例如 echarts 只有在打开回测页面时才会被引入）
const StrategyPage = lazy(() => import('./components/StrategyPage'))
const BacktestPage = lazy(() => import('./components/BacktestPage'))
const AIChatPage = lazy(() => import('./components/AIChatPage'))
const SettingsPage = lazy(() => import('./components/SettingsPage'))

const TAB_KEYS = ['trading', 'strategy', 'backtest', 'ai', 'settings'] as const

function lazyTab(node: React.ReactNode) {
  return (
    <Suspense
      fallback={
        <div style={{ padding: 48, textAlign: 'center' }}>
          <Spin />
        </div>
      }
    >
      {node}
    </Suspense>
  )
}

/** 挂载感知主题的通知实例并交给全局通知器
 *（必须位于 ConfigProvider 内部）。 */
function NotificationBridge() {
  const [notifApi, contextHolder] = notification.useNotification({
    maxCount: 5,
    stack: { threshold: 3 },
  })

  useEffect(() => {
    setNotifier(notifApi)
    return () => setNotifier(null)
  }, [notifApi])

  return contextHolder
}

function App() {
  const mode = useThemeStore(s => s.mode)
  const [authChecked, setAuthChecked] = useState(false)
  const username = useAuthStore(s => s.username)
  const checkAuth = useAuthStore(s => s.checkAuth)

  // 启动时验证 token
  useEffect(() => {
    checkAuth().finally(() => setAuthChecked(true))
  }, [checkAuth])

  // 登录后才启动 WebSocket
  useEffect(() => {
    if (username) {
      wsClient.start()
      return () => wsClient.stop()
    }
  }, [username])

  // URL 路径 -> 当前 Tab（HashRouter 下 pathname 取自 hash）；
  // 未知路径回落到 trading，保证总有激活的 Tab。
  const navigate = useNavigate()
  const location = useLocation()
  const pathTab =
    location.pathname === '/' ? 'trading' : location.pathname.slice(1).split('/')[0]
  const activeTab = (TAB_KEYS as readonly string[]).includes(pathTab) ? pathTab : 'trading'

  if (!authChecked) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!username) {
    return <LoginPage />
  }

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm:
          mode === 'dark'
            ? antdTheme.darkAlgorithm
            : antdTheme.defaultAlgorithm,
        token: {
          borderRadius: 4,
        },
      }}
    >
      <div
        style={{
          // minHeight 而非 height：长页面（策略/设置）滚动时背景与极光随内容延伸
          minHeight: '100%',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          background: mode === 'dark' ? '#020617' : '#f8fafc',
        }}
      >
        <AuroraBackground />
        <div
          className="glass-ui relative z-10 flex min-h-0 flex-1 flex-col"
        >
          <NotificationBridge />
          <HeaderBar />
          <Tabs
            activeKey={activeTab}
            onChange={key => navigate(`/${key}`)}
            style={{ flex: 1, minHeight: 0, padding: '0 12px' }}
            tabBarStyle={{ marginBottom: 8 }}
          items={[
            {
              key: 'trading',
              label: '交易',
              children: <TradingPage />,
              forceRender: true,
            },
            { key: 'strategy', label: '策略', children: lazyTab(<StrategyPage />) },
            { key: 'backtest', label: '回测', children: lazyTab(<BacktestPage />) },
            { key: 'ai', label: 'AI 助手', children: lazyTab(<AIChatPage />) },
            { key: 'settings', label: '设置', children: lazyTab(<SettingsPage />) },
          ]}
          />
        </div>
      </div>
    </ConfigProvider>
  )
}

export default App