import { Component, ErrorInfo, PropsWithChildren, ReactNode } from "react";
import { Button } from "@/shared/ui/button";

type ErrorBoundaryState = {
  hasError: boolean;
  errorMessage: string;
};

export class ErrorBoundary extends Component<
  PropsWithChildren,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {
    hasError: false,
    errorMessage: "",
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || "Unexpected UI error.",
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="w-full max-w-md rounded-lg border bg-background p-6 text-center shadow-sm">
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {this.state.errorMessage}
            </p>
            <Button className="mt-4" onClick={this.handleReload}>
              Reload app
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
