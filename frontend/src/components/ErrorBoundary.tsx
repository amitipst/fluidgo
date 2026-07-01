import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('fluidGo crashed:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-wep-surface p-6">
          <div className="card max-w-sm text-center">
            <div className="text-3xl mb-2">⚠️</div>
            <h1 className="font-display font-bold text-wep-navy mb-1">Something went wrong</h1>
            <p className="text-sm text-wep-muted mb-4">
              fluidGo hit an unexpected error. Reloading usually fixes it.
            </p>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
