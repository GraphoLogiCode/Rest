import { useEffect, useState, type FormEvent } from "react";
import { supabase } from "../services/cloudSession";

export function CloudSignIn() {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [user, setUser] = useState<string | null>(null),
    [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false),
    [mode, setMode] = useState("signin");
  const [recovery, setRecovery] = useState(
    new URLSearchParams(location.search).get("reset") === "1",
  );
  useEffect(() => {
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      setUser(session?.user.email || null);
      if (event === "PASSWORD_RECOVERY") setRecovery(true);
    });
    return () => data.subscription.unsubscribe();
  }, []);
  if (!supabase)
    return (
      <p className="notice">
        Account sign-in will be available once the saved-account service is
        connected.
      </p>
    );
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      if (recovery && user) {
        const { error } = await supabase!.auth.updateUser({ password });
        if (error) throw error;
        setRecovery(false);
        history.replaceState(null, "", location.pathname + "#settings");
        setMessage("Password updated.");
      } else if (mode === "reset") {
        const { error } = await supabase!.auth.resetPasswordForEmail(email, {
          redirectTo: location.origin + location.pathname + "?reset=1#settings",
        });
        if (error) throw error;
        setMessage(
          "If this address can receive a recovery email, check your inbox for the link.",
        );
      } else if (mode === "signup") {
        const { data, error } = await supabase!.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: location.origin + location.pathname + "#settings",
          },
        });
        if (error) throw error;
        setMessage(
          data.session
            ? "Account created. Choose your saving preferences below."
            : "Check your email to confirm your account, then sign in.",
        );
      } else {
        const { error } = await supabase!.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
      }
    } catch {
      setMessage(
        mode === "signin"
          ? "Could not sign in. Check your email and password."
          : "Could not complete this request. Check your details and try again; email delivery must be configured for new accounts and recovery.",
      );
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  const resetting = recovery && !!user;
  return (
    <div className="cloud-session">
      {user && !resetting ? (
        <>
          <p>Signed in as {user}</p>
          <button
            className="button secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              const { error } = await supabase!.auth.signOut();
              setBusy(false);
              if (error) setMessage("Could not sign out. Please try again.");
            }}
          >
            Sign out
          </button>
        </>
      ) : (
        <form onSubmit={submit}>
          <p>
            {resetting
              ? "Choose a new password."
              : "Sign in or create an account to save check-ins, routines and real photo comparisons."}
          </p>
          {!resetting && (
            <label className="field">
              Email
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          )}
          {(resetting || mode !== "reset") && (
            <label className="field">
              Password
              <input
                type="password"
                autoComplete={
                  mode === "signup" || resetting
                    ? "new-password"
                    : "current-password"
                }
                minLength={mode === "signup" || resetting ? 12 : undefined}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          )}
          {(mode === "signup" || resetting) && (
            <p className="small-text">Use at least 12 characters.</p>
          )}
          <button className="button primary" disabled={busy}>
            {busy
              ? "Working…"
              : resetting
                ? "Update password"
                : mode === "signup"
                  ? "Create account"
                  : mode === "reset"
                    ? "Send recovery email"
                    : "Sign in"}
          </button>
          {!resetting && (
            <div className="form-row">
              {[
                ["signin", "Sign in"],
                ["signup", "Create account"],
                ["reset", "Forgot password"],
              ]
                .filter(([id]) => id !== mode)
                .map(([id, title]) => (
                  <button
                    className="button secondary"
                    type="button"
                    disabled={busy}
                    key={id}
                    onClick={() => {
                      setMode(id);
                      setMessage("");
                      setPassword("");
                    }}
                  >
                    {title}
                  </button>
                ))}
            </div>
          )}
        </form>
      )}
      {message && <p role="status">{message}</p>}
    </div>
  );
}
