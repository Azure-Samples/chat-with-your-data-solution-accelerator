/**
 * React error boundary for the chat surface. A render-time throw in any
 * descendant (a malformed message, an unexpected stream / citation
 * shape) would otherwise unmount the whole React tree to a blank page.
 * This boundary catches it via `getDerivedStateFromError` and renders a
 * recoverable fallback in place -- a heading, the error message, and a
 * "Try again" button that clears the error and re-renders the children.
 *
 * Error boundaries must be class components -- there is no hook
 * equivalent for `getDerivedStateFromError` -- so this is the sole class
 * component in the frontend.
 */
import { Button, Text } from "@fluentui/react-components";
import { Component, type ReactNode } from "react";
import styles from "./ErrorBoundary.module.css";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    // Coerce non-Error throws so the fallback can always read `.message`.
    return {
      error: error instanceof Error ? error : new Error(String(error)),
    };
  }

  private readonly handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (error === null) {
      return this.props.children;
    }
    return (
      <section
        className={styles.container}
        role="alert"
        data-testid="error-boundary-fallback"
      >
        <Text as="h2" className={styles.title} weight="semibold">
          Something went wrong
        </Text>
        <Text as="p" className={styles.message}>
          {error.message}
        </Text>
        <Button appearance="primary" onClick={this.handleReset}>
          Try again
        </Button>
      </section>
    );
  }
}
