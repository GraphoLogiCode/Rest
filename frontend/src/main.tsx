import { Component, lazy, Suspense, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { LoadingScreen } from "./components/LoadingScreen";
import "./styles.css";
import { setupPwa } from "./services/pwa";
setupPwa(import.meta.env.PROD);
const App = lazy(() => import("./App"));
class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <LoadingScreen
        error="We couldn’t load your space. Try again."
        onRetry={() => window.location.reload()}
      />
    ) : (
      this.props.children
    );
  }
}
// Reuse the root if Vite refreshes this entry module during development.
const root: Root =
  import.meta.hot?.data.root ?? createRoot(document.getElementById("root")!);
if (import.meta.hot) import.meta.hot.data.root = root;
root.render(
  <ErrorBoundary>
    <Suspense fallback={<LoadingScreen />}>
      <App />
    </Suspense>
  </ErrorBoundary>,
);
