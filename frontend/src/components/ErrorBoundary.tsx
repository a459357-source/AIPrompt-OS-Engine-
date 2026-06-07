import { Component, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[ErrorBoundary]', error.message, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-6 text-center px-4">
          <div className="text-5xl">💥</div>
          <h2 className="text-lg font-bold text-game-danger">页面出错了</h2>
          <p className="text-game-muted text-sm max-w-md">
            {this.state.error?.message || '发生了未预期的错误'}
          </p>
          <p className="text-game-dim text-xs max-w-md">
            这可能是网络问题或临时故障，请尝试刷新页面。
          </p>
          <div className="flex gap-3 flex-wrap justify-center">
            <Button variant="outline" onClick={this.handleReset}>
              🔄 刷新页面
            </Button>
            <Button variant="ghost" onClick={this.handleGoHome}>
              🏠 返回首页
            </Button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
