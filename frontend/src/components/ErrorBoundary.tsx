import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Card, Typography } from 'antd'

const { Text, Title } = Typography

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/** 全局错误边界：捕获渲染错误，显示错误信息而非黑屏。 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('页面渲染错误:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            height: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
        >
          <Card style={{ maxWidth: 600, width: '100%' }}>
            <Title level={4} style={{ color: '#f5455c' }}>
              页面出错了
            </Title>
            <Text type="secondary">遇到一个问题，请把下面的错误信息反馈给开发者。</Text>
            <pre
              style={{
                marginTop: 16,
                padding: 12,
                background: 'rgba(0,0,0,0.05)',
                borderRadius: 4,
                overflow: 'auto',
                maxHeight: 300,
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {this.state.error.message}
            </pre>
            <Button
              type="primary"
              style={{ marginTop: 16 }}
              onClick={() => {
                localStorage.removeItem('auth_token')
                window.location.href = '/'
              }}
            >
              刷新页面
            </Button>
          </Card>
        </div>
      )
    }
    return this.props.children
  }
}