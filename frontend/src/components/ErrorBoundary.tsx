import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Compact (in-page) fallback instead of full-screen — use per-route. */
  compact?: boolean;
  /**
   * When any value in this array changes, the boundary resets and re-renders
   * children. Pass the route path so navigating away clears a page crash.
   */
  resetKeys?: ReadonlyArray<unknown>;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error);
    console.error('Error info:', errorInfo.componentStack);
  }

  componentDidUpdate(prevProps: Props): void {
    // Reset the error when resetKeys change (e.g. route navigation).
    if (this.state.hasError && this.props.resetKeys !== prevProps.resetKeys) {
      const prev = prevProps.resetKeys ?? [];
      const next = this.props.resetKeys ?? [];
      const changed =
        prev.length !== next.length || next.some((k, i) => k !== prev[i]);
      if (changed) {
        this.setState({ hasError: false, error: null });
      }
    }
  }

  handleReload = (): void => {
    if (this.props.compact) {
      // In-page recovery: clear the error and re-render children.
      this.setState({ hasError: false, error: null });
    } else {
      window.location.reload();
    }
  };

  render(): ReactNode {
    if (this.state.hasError) {
      const compact = this.props.compact;
      const wrapperClass = compact
        ? 'flex items-center justify-center p-8'
        : 'min-h-screen flex items-center justify-center bg-gray-50';
      return (
        <div className={wrapperClass} role="alert">
          <div className="text-center p-8 bg-white rounded-lg shadow-lg max-w-md">
            <div className="text-red-500 mb-4">
              <svg
                className="w-16 h-16 mx-auto"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              Κάτι πήγε στραβά
            </h1>
            <p className="text-gray-600 mb-6">
              Παρουσιάστηκε ένα απροσδόκητο σφάλμα. Παρακαλώ δοκιμάστε ξανά.
            </p>
            <button
              onClick={this.handleReload}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors"
            >
              {compact ? 'Δοκιμάστε ξανά' : 'Επαναφόρτωση'}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
