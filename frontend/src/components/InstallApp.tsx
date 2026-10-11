import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import {
  installApp,
  installedApp,
  pwaState,
  subscribePwa,
  updateApp,
} from "../services/pwa";

export function InstallApp() {
  const [state, setState] = useState(pwaState),
    [installed, setInstalled] = useState(installedApp);
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(
    () =>
      subscribePwa(() => {
        setState(pwaState());
        setInstalled(installedApp());
      }),
    [],
  );
  const secure = window.isSecureContext;
  return (
    <section className="panel install-panel" aria-labelledby="install-title">
      <Download size={24} aria-hidden="true" />
      <h2 id="install-title">Keep Rest on your phone.</h2>
      {installed ? (
        <p>Rest is open as an installed app.</p>
      ) : (
        <>
          <p>
            Add Rest to your home screen for an app icon and its own window.
            Your account stays connected to the same Rest service.
          </p>
          {state.canPrompt && (
            <button
              className="button primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setMessage("");
                try {
                  await installApp();
                } catch {
                  setMessage(
                    "Use your browser’s installation menu to add Rest.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Install Rest <Download size={17} />
            </button>
          )}
          {!secure && (
            <p className="notice">
              Phone installation becomes available at Rest’s hosted HTTPS
              address.
            </p>
          )}
          <div className="install-instructions">
            <p>
              <strong>iPhone:</strong> Open Rest in Safari, open the Share menu,
              choose Add to Home Screen, and enable Open as Web App if shown.
            </p>
            <p>
              <strong>Android:</strong> Open Rest in Chrome, then choose Install
              app or Add to Home screen from the browser menu.
            </p>
          </div>
          <p className="small-text">
            Account saving, recommendations and photo uploads need an internet
            connection.
          </p>
        </>
      )}
      {state.updateReady && (
        <div className="notice">
          <p>
            A Rest update is ready. Save your changes before updating; temporary
            comparison photos will clear.
          </p>
          <button className="button secondary" onClick={updateApp}>
            Update Rest
          </button>
        </div>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
export function ConnectionStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const check = () => setOnline(navigator.onLine);
    window.addEventListener("online", check);
    window.addEventListener("offline", check);
    return () => {
      window.removeEventListener("online", check);
      window.removeEventListener("offline", check);
    };
  }, []);
  return online ? null : (
    <p className="notice connection-notice" role="status">
      You’re offline. Reconnect to save account updates, get recommendations or
      upload photos.
    </p>
  );
}
