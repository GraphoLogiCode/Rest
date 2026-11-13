import { Loops, Wordmark } from "./Brand";

export function LoadingScreen({
  status = "Loading your space…",
  progress,
  error,
  onRetry,
  onClose,
}: {
  status?: string;
  progress?: number;
  error?: string;
  onRetry?: () => void;
  onClose?: () => void;
}) {
  return (
    <div className="loading-screen">
      {onClose && (
        <button className="button ghost loading-close" onClick={onClose}>
          Back to your space
        </button>
      )}
      <div className="loading-content">
        <Loops />
        <Wordmark />
        <p>A little space for you.</p>
        {error ? (
          <div role="alert">
            <p>{error}</p>
            {onRetry && (
              <button className="button primary" onClick={onRetry}>
                Try again
              </button>
            )}
          </div>
        ) : (
          <>
            <div
              className={`progress-line ${progress === undefined ? "indeterminate" : ""}`}
              role="progressbar"
              aria-label={status}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={
                progress === undefined
                  ? undefined
                  : Math.min(100, Math.max(0, progress))
              }
            >
              <span
                style={
                  progress === undefined
                    ? undefined
                    : { width: `${Math.min(100, Math.max(0, progress))}%` }
                }
              />
            </div>
            <p className="loading-status" role="status">
              {status}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
