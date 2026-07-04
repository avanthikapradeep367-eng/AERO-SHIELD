import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("AERO-SHIELD console crashed:", error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;

    if (!error) {
      return this.props.children;
    }

    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-danger">Console error</p>
        <h1 className="text-xl font-semibold text-ink">Something went wrong rendering this view.</h1>
        <p className="max-w-md text-sm text-ink-muted">{error.message}</p>
        <button
          type="button"
          onClick={this.handleReset}
          className="rounded-md border border-line bg-surface-raised px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-accent hover:text-accent"
        >
          Try again
        </button>
      </div>
    );
  }
}
