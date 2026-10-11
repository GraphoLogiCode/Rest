type InstallPrompt = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};
let installPrompt: InstallPrompt | null = null;
let waiting: ServiceWorker | null = null;
let initialized = false;
let appInstalled = false;
const subscribers = new Set<() => void>();
function publish() {
  for (const callback of subscribers) callback();
}
export function subscribePwa(callback: () => void) {
  subscribers.add(callback);
  return () => {
    subscribers.delete(callback);
  };
}
export function pwaState() {
  return { canPrompt: installPrompt !== null, updateReady: waiting !== null };
}
export function installedApp() {
  return (
    appInstalled ||
    window.matchMedia("(display-mode: standalone)").matches ||
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
  );
}
export async function installApp() {
  const event = installPrompt;
  if (!event) return;
  installPrompt = null;
  publish();
  await event.prompt();
  await event.userChoice;
}
export function updateApp() {
  if (!waiting) return;
  navigator.serviceWorker.addEventListener(
    "controllerchange",
    () => location.reload(),
    { once: true },
  );
  waiting.postMessage({ type: "SKIP_WAITING" });
}
export function setupPwa(production: boolean) {
  if (initialized) return;
  initialized = true;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event as InstallPrompt;
    publish();
  });
  window.addEventListener("appinstalled", () => {
    appInstalled = true;
    installPrompt = null;
    publish();
  });
  if (!production || !("serviceWorker" in navigator) || !window.isSecureContext)
    return;
  const register = async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
        updateViaCache: "none",
      });
      if (registration.waiting) {
        waiting = registration.waiting;
        publish();
      }
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (
            worker.state === "installed" &&
            navigator.serviceWorker.controller
          ) {
            waiting = worker;
            publish();
          }
        });
      });
    } catch {
      // Installation remains usable through the browser without offline caching.
    }
  };
  if (document.readyState === "complete") void register();
  else window.addEventListener("load", () => void register(), { once: true });
}
