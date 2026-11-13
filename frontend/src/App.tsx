import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Heart,
  House,
  Leaf,
  Menu,
  Moon,
  Plus,
  Settings,
  ShieldCheck,
  Sparkles,
  Sprout,
  Sun,
  Trash2,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { Botanical, Loops, Wordmark } from "./components/Brand";
import { LoadingScreen } from "./components/LoadingScreen";
import { Journal, type Photo } from "./components/Journal";
import {
  createLocalId,
  deleteData,
  emptyData,
  localDate,
  type CheckIn,
  type RestData,
  type RoutineStep,
} from "./services/storage";

import { ProductCatalog } from "./components/ProductCatalog";
import { useAccountData } from "./hooks/useAccountData";
import { CloudSignIn } from "./components/CloudSignIn";
import { accountApi } from "./services/accountApi";
import { InstallApp, ConnectionStatus } from "./components/InstallApp";

type Page =
  | "overview"
  | "check-in"
  | "routine"
  | "journal"
  | "settings"
  | "products";
const nav: { id: Page; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "My space", icon: House },
  { id: "check-in", label: "Daily check-in", icon: Heart },
  { id: "routine", label: "My routine", icon: Sprout },
  { id: "products", label: "Products & suggestions", icon: Leaf },
  { id: "journal", label: "Skin journal", icon: Sparkles },
];
function currentPage(): Page {
  if (new URLSearchParams(window.location.search).get("reset") === "1")
    return "settings";
  const hash = window.location.hash.slice(1);
  return [...nav.map((n) => n.id), "settings"].includes(hash)
    ? (hash as Page)
    : "overview";
}
function prettyDate(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage);
  const account = useAccountData();
  const { data, setData } = account;
  const [photos, setPhotos] = useState<(Photo | null)[]>([null, null]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const main = useRef<HTMLElement>(null);
  useEffect(() => {
    setPhotos((previous) => {
      previous.forEach((p) => p && URL.revokeObjectURL(p.url));
      return [null, null];
    });
  }, [account.user]);
  const today = localDate();
  const checkIn = data.checkIns.find((c) => c.date === today);
  useEffect(() => {
    const onHash = () => {
      if (window.location.hash === "#main-content") {
        main.current?.focus();
        return;
      }
      setPage(currentPage());
      setMobileOpen(false);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  function navigate(next: Page) {
    window.location.hash = next;
    setPage(next);
    setMobileOpen(false);
    setDeleteConfirm(false);
    window.scrollTo({ top: 0 });
    main.current?.focus();
  }
  async function update(next: RestData) {
    const success = await account.update(next);
    if (success)
      setNotice(
        account.cloud ? "Saved to your account." : "Saved on this device.",
      );
    return success;
  }
  function toggleStep(id: string) {
    update({
      ...data,
      routine: data.routine.map((s) =>
        s.id === id
          ? { ...s, completedOn: s.completedOn === today ? undefined : today }
          : s,
      ),
    });
  }
  async function clearAll() {
    if (account.cloud) {
      if (!(await account.clearAccount())) return;
      photos.forEach((p) => p && URL.revokeObjectURL(p.url));
      setPhotos([null, null]);
      setDeleteConfirm(false);
      setNotice("Account data deleted. Your sign-in identity remains.");
      return;
    }
    try {
      deleteData();
    } catch {
      setNotice("Browser storage couldn’t be cleared. Please try again.");
      return;
    }
    setData(emptyData);
    photos.forEach((p) => p && URL.revokeObjectURL(p.url));
    setPhotos([null, null]);
    setDeleteConfirm(false);
    setNotice("Your local data and photos have been cleared.");
  }
  async function exportData() {
    let exported: unknown = data;
    if (account.cloud) {
      try {
        exported = await accountApi(
          "/v1/export",
          { method: "POST" },
          account.user || undefined,
        );
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Export failed.");
        return;
      }
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(exported, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `rest-journal-${today}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  if (loadingPreview)
    return <LoadingScreen onClose={() => setLoadingPreview(false)} />;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="mobile-top">
        <button
          className="icon-button"
          aria-label="Open navigation"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen(true)}
        >
          <Menu />
        </button>
        <Wordmark />
        <span className="avatar">you</span>
      </div>
      {mobileOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <a
          className="brand-link"
          href="#overview"
          onClick={() => navigate("overview")}
        >
          <Wordmark />
          <span>A LITTLE SPACE FOR YOU</span>
        </a>
        <button
          className="mobile-close icon-button"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        >
          <X />
        </button>
        <div className="nav-label">YOUR EVERYDAY</div>
        <nav aria-label="Main navigation">
          {nav.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={`#${id}`}
              className={`nav-item ${page === id ? "active" : ""}`}
              aria-current={page === id ? "page" : undefined}
              onClick={(e) => {
                e.preventDefault();
                navigate(id);
              }}
            >
              <Icon size={19} />
              <span>{label}</span>
              {page === id && <span className="nav-dot" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Leaf size={22} />
            <p>
              Small steps.
              <br />A little more you.
            </p>
            <span>There’s no perfect way to begin.</span>
          </div>
          <a
            href="#settings"
            className={`nav-item ${page === "settings" ? "active" : ""}`}
            onClick={(e) => {
              e.preventDefault();
              navigate("settings");
            }}
          >
            <Settings size={18} /> Settings & privacy
          </a>
          <div className="sidebar-profile">
            <span className="avatar">you</span>
            <div>
              <strong>Your personal space</strong>
              <span>
                {account.cloud
                  ? account.user
                    ? "Account storage"
                    : "Sign in to save"
                  : "Stored on this device"}
              </span>
            </div>
          </div>
        </div>
      </aside>
      <main id="main-content" ref={main} tabIndex={-1}>
        <header className="topbar">
          <span>
            {page === "overview"
              ? "Your well-being, at your pace."
              : "A little space for you."}
          </span>
          <div>
            <span className="today-date">
              {new Date().toLocaleDateString(undefined, {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </span>
            <span className="local-badge">
              <span /> PERSONAL PREVIEW
            </span>
          </div>
        </header>
        <div className="page-content">
          <ConnectionStatus />
          {account.cloud && (
            <section
              className="panel account-panel"
              style={{ padding: 20, marginBottom: 20 }}
            >
              <CloudSignIn />
              {account.user && (
                <>
                  {!account.ready && !account.error && (
                    <p role="status">Loading account data…</p>
                  )}
                  {account.ready && !account.consent && (
                    <>
                      <p>
                        Enable saving check-ins (including sleep, mood and
                        connection) and routines to your account. This does not
                        allow model training or photo storage.
                      </p>
                      <button
                        className="button primary"
                        disabled={account.busy}
                        onClick={() => void account.enable()}
                      >
                        Agree and enable account saving
                      </button>
                    </>
                  )}
                  <button
                    className="button secondary"
                    disabled={account.busy}
                    onClick={() => void account.reload()}
                  >
                    Reload account data
                  </button>
                  {account.consent && (
                    <details>
                      <summary>Import this browser’s existing notes</summary>
                      <p>
                        This copies local check-ins and routine steps to the
                        signed-in account. Existing account check-in dates win;
                        local originals remain on this device. A partially
                        completed import can be retried.
                      </p>
                      <button
                        className="button secondary"
                        disabled={account.busy}
                        onClick={() => void account.importLocal()}
                      >
                        Import local entries into this account
                      </button>
                    </details>
                  )}
                </>
              )}
            </section>
          )}
          {account.error && (
            <p className="notice error" role="alert">
              {account.error} Your changes may not have been saved. Reload
              account data before retrying.
            </p>
          )}
          {account.busy && <p role="status">Saving or loading account data…</p>}
          {page === "overview" && (
            <>
              <section className="welcome">
                <div className="welcome-copy">
                  <span className="eyebrow">
                    <span /> ROOM TO SLOW DOWN
                  </span>
                  <h1>
                    A little space
                    <br />
                    for yourself.
                  </h1>
                  <p>
                    Your skin, your routines, your well-being.
                    <br />
                    Come as you are. Start where you are.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => navigate("check-in")}
                  >
                    {checkIn
                      ? "Revisit today’s check-in"
                      : "Take a moment to check in"}
                    <ArrowRight size={17} />
                  </button>
                  <span className="welcome-caption">
                    A small pause can be a lovely place to start.
                  </span>
                </div>
                <Botanical />
                <span className="hero-note">grow at your own pace</span>
              </section>
              <section className="wellbeing-section">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">THE WHOLE YOU</span>
                    <h2>How are you, really?</h2>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => navigate("check-in")}
                  >
                    {checkIn ? "Edit check-in" : "Your daily check-in"}
                    <ArrowRight size={16} />
                  </button>
                </div>
                <div className="pillar-grid">
                  {[
                    {
                      title: "Sleep",
                      subtitle: "A little room to recharge.",
                      value: checkIn
                        ? checkIn.sleep === null
                          ? "Not logged"
                          : `${checkIn.sleep} hours`
                        : "How did you rest?",
                      icon: Moon,
                      color: "lavender",
                      footer: checkIn
                        ? "Your last night, noted"
                        : "Reflect on last night",
                    },
                    {
                      title: "Mental well-being",
                      subtitle: "Every feeling has a place.",
                      value: checkIn ? checkIn.mood : "What’s on your mind?",
                      icon: Sun,
                      color: "sage",
                      footer: checkIn
                        ? "Your mood today"
                        : "Notice how you feel",
                    },
                    {
                      title: "Connection",
                      subtitle: "Your kind of togetherness.",
                      value: checkIn ? checkIn.social : "Feeling connected?",
                      icon: Users,
                      color: "peach",
                      footer: checkIn
                        ? "Your connection today"
                        : "A moment for connection",
                    },
                  ].map(
                    ({ title, subtitle, value, icon: Icon, color, footer }) => (
                      <button
                        className={`pillar-card ${color}`}
                        key={title}
                        onClick={() => navigate("check-in")}
                      >
                        <span className="pillar-top">
                          <span className="pillar-icon">
                            <Icon size={21} />
                          </span>
                          <span className="small-circle">
                            {checkIn ? <Check size={14} /> : <Plus size={14} />}
                          </span>
                        </span>
                        <h3>{title}</h3>
                        <p>{subtitle}</p>
                        <strong>{value}</strong>
                        <span className="pillar-footer">
                          {footer}
                          <ArrowRight size={15} />
                        </span>
                      </button>
                    ),
                  )}
                </div>
              </section>
              <div className="dashboard-bottom">
                <section className="panel routine-preview">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">LITTLE RITUALS</span>
                      <h2>Care, one step at a time.</h2>
                    </div>
                    <Sprout className="muted-icon" size={24} />
                  </div>
                  {data.routine.length ? (
                    <div className="routine-list">
                      {data.routine.slice(0, 3).map((step) => (
                        <RoutineRow
                          key={step.id}
                          step={step}
                          onToggle={() => toggleStep(step.id)}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="empty-routine">
                      <span className="empty-line-icon">
                        <Sun size={22} />
                      </span>
                      <div>
                        <strong>Your routine starts with you.</strong>
                        <p>
                          Add the little rituals that feel right for your day.
                        </p>
                      </div>
                    </div>
                  )}
                  <button
                    className="text-button"
                    onClick={() => navigate("routine")}
                  >
                    {data.routine.length
                      ? "Open my routine"
                      : "Build my routine"}
                    <ArrowRight size={16} />
                  </button>
                </section>
                <section className="panel journal-preview">
                  <div className="journal-preview-copy">
                    <span className="eyebrow">YOUR SKIN STORY</span>
                    <h2>
                      Notice the
                      <br />
                      little changes.
                    </h2>
                    <p>
                      A photo today. A little
                      <br />
                      perspective tomorrow.
                    </p>
                    <button
                      className="text-button"
                      onClick={() => navigate("journal")}
                    >
                      Open skin journal
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  <div className="photo-stack" aria-hidden="true">
                    <div className="paper-photo back">
                      <span />
                    </div>
                    <div className="paper-photo front">
                      <div>
                        <Leaf size={37} strokeWidth={1} />
                      </div>
                      <span>one day at a time</span>
                    </div>
                    <span className="photo-spark">✧</span>
                  </div>
                </section>
              </div>
              <footer className="daily-note">
                <span>
                  <Leaf size={16} /> A GENTLE REMINDER
                </span>
                <p>
                  You don’t have to do it all. A little care is enough for
                  today.
                </p>
                <span className="note-decoration">✧</span>
              </footer>
            </>
          )}
          {page === "check-in" && (
            <fieldset
              className="account-fields"
              disabled={
                account.busy ||
                (account.cloud && (!account.ready || !account.consent))
              }
            >
              <CheckInPage
                key={account.user || "local"}
                cloud={account.cloud}
                existing={checkIn}
                history={data.checkIns}
                onSave={(entry) =>
                  void update({
                    ...data,
                    checkIns: [
                      ...data.checkIns.filter((c) => c.date !== entry.date),
                      entry,
                    ],
                  })
                }
              />
            </fieldset>
          )}
          {page === "routine" && (
            <fieldset
              className="account-fields"
              disabled={
                account.busy ||
                (account.cloud && (!account.ready || !account.consent))
              }
            >
              <RoutinePage
                steps={data.routine}
                onToggle={toggleStep}
                onAdd={(step) =>
                  update({ ...data, routine: [...data.routine, step] })
                }
                onRemove={(id) =>
                  update({
                    ...data,
                    routine: data.routine.filter((s) => s.id !== id),
                  })
                }
              />
            </fieldset>
          )}
          {page === "products" && (
            <ProductCatalog
              key={account.user || "local"}
              user={account.user}
              canSave={
                account.cloud &&
                account.ready &&
                account.consent &&
                !account.busy
              }
              onAdd={(step) =>
                update({ ...data, routine: [...data.routine, step] })
              }
            />
          )}
          {page === "journal" && (
            <Journal
              key={account.user || "local"}
              photos={photos}
              setPhotos={setPhotos}
              user={account.user}
              canSave={
                account.cloud &&
                account.ready &&
                account.consent &&
                !account.busy
              }
            />
          )}
          {page === "settings" && (
            <>
              <div className="page-intro">
                <span className="eyebrow">YOUR SPACE, YOUR CHOICE</span>
                <h1>A little peace of mind.</h1>
                <p>You’re in control of what you keep here.</p>
              </div>
              <InstallApp />
              <section className="panel settings-panel">
                <ShieldCheck size={28} />
                <h2>
                  {account.cloud
                    ? "Your saved account data"
                    : "Your notes stay on this device."}
                </h2>
                <p>
                  {account.cloud
                    ? "Check-ins and routines are saved to your signed-in account after you enable saving. Existing local entries are imported only when you choose to import them."
                    : "Check-ins and routines are saved in this browser’s local storage. They are not synced to an account. Use a device you trust."}
                </p>
                <p>
                  Temporary comparison photos stay in this tab. With separate
                  photo-storage permission, the saved journal keeps real photos
                  in your account. You can download or delete them there.
                  Revoking photo storage deletes saved photos from active
                  storage. Product-use reports and recommendation feedback are
                  included in your account export. Training permission is
                  separate and optional; no training or outcome prediction is
                  running.
                </p>
                <div className="settings-row">
                  <div>
                    <h3>Take your notes with you</h3>
                    <p>
                      Download saved records as JSON, including progress
                      metadata. Download saved photo files separately in the
                      journal.
                    </p>
                  </div>
                  <button
                    className="button secondary"
                    disabled={account.cloud && !account.user}
                    onClick={exportData}
                  >
                    <ArrowDownToLine size={16} /> Export my data
                  </button>
                </div>
                <div className="settings-row">
                  <div>
                    <h3>A fresh start</h3>
                    <p>
                      {account.cloud
                        ? "Delete your account profile, check-ins, routines, consent records, insights, saved photos, product-use reports, recommendation feedback and temporary previews. This does not delete the sign-in identity or local browser entries."
                        : "Delete all Rest check-ins, routines, and photos on this device."}
                    </p>
                  </div>
                  <button
                    className="button danger"
                    disabled={account.cloud && !account.user}
                    onClick={() => setDeleteConfirm(true)}
                  >
                    <Trash2 size={16} />{" "}
                    {account.cloud ? "Delete account data" : "Clear local data"}
                  </button>
                </div>
                {deleteConfirm && (
                  <div className="delete-confirm" role="alert">
                    <p>
                      {account.cloud
                        ? "Permanently delete all your saved account data?"
                        : "Permanently delete your saved local notes and routine?"}
                    </p>
                    <button className="button danger" onClick={clearAll}>
                      Yes, clear my data
                    </button>
                    <button
                      className="button secondary"
                      onClick={() => setDeleteConfirm(false)}
                    >
                      Keep my data
                    </button>
                  </div>
                )}
                <div className="settings-row">
                  <div>
                    <h3>A moment of calm</h3>
                    <p>
                      Preview Rest’s loading screen and three well-being loops.
                    </p>
                  </div>
                  <button
                    className="button secondary"
                    onClick={() => setLoadingPreview(true)}
                  >
                    Preview loading screen
                  </button>
                </div>
              </section>
              <div className="brand-reference panel">
                <img
                  src="/rest-brand-reference.png"
                  alt="Original Rest brand reference: forest green and gold wordmark with botanical leaves"
                />
                <div>
                  <span className="eyebrow">ROOTED IN YOUR VISION</span>
                  <h2>Care that feels natural.</h2>
                  <p>
                    Your original logo inspires this space’s botanical details,
                    warm paper tones, and forest green wordmark.
                  </p>
                </div>
              </div>
            </>
          )}
          <div className="page-footer">
            <span>
              <Loops /> Rest. A little space for you.
            </span>
            <button onClick={() => navigate("settings")}>
              <CircleHelp size={14} /> Your data & privacy
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </main>
      {notice && (
        <div className="toast" role="status">
          <CheckCheck size={19} />
          {notice}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function RoutineRow({
  step,
  onToggle,
  onRemove,
}: {
  step: RoutineStep;
  onToggle: () => void;
  onRemove?: () => void;
}) {
  const completed = step.completedOn === localDate();
  return (
    <div className={`routine-row ${completed ? "completed" : ""}`}>
      <button
        className={`check-button ${completed ? "checked" : ""}`}
        role="checkbox"
        aria-checked={completed}
        aria-label={`Complete ${step.name}`}
        onClick={onToggle}
      >
        {completed && <Check size={15} />}
      </button>
      <div>
        <strong>{step.name}</strong>
        <span>
          {step.period === "morning" ? "Morning ritual" : "Evening ritual"}
        </span>
      </div>
      {onRemove ? (
        <button
          className="icon-button"
          aria-label={`Remove ${step.name}`}
          onClick={onRemove}
        >
          <Trash2 size={16} />
        </button>
      ) : (
        <span className="step-period">
          {step.period === "morning" ? <Sun size={16} /> : <Moon size={16} />}
        </span>
      )}
    </div>
  );
}
function RoutinePage({
  steps,
  onToggle,
  onAdd,
  onRemove,
}: {
  steps: RoutineStep[];
  onToggle: (id: string) => void;
  onAdd: (step: RoutineStep) => Promise<boolean>;
  onRemove: (id: string) => void;
}) {
  const [period, setPeriod] = useState<"morning" | "evening">("morning");
  const [name, setName] = useState("");
  async function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    if (await onAdd({ id: createLocalId(), name: name.trim(), period }))
      setName("");
  }
  const filtered = steps.filter((s) => s.period === period);
  return (
    <>
      <div className="page-intro">
        <span className="eyebrow">LITTLE RITUALS</span>
        <h1>Make care your own.</h1>
        <p>A routine that fits your life, one small step at a time.</p>
      </div>
      <section className="panel routine-panel">
        <div className="section-heading">
          <h2>Your everyday routine</h2>
          <div className="segmented">
            <button
              className={period === "morning" ? "active" : ""}
              onClick={() => setPeriod("morning")}
            >
              <Sun size={16} /> Morning
            </button>
            <button
              className={period === "evening" ? "active" : ""}
              onClick={() => setPeriod("evening")}
            >
              <Moon size={16} /> Evening
            </button>
          </div>
        </div>
        <p className="small-text">
          {filtered.filter((s) => s.completedOn === localDate()).length} of{" "}
          {filtered.length} steps completed today. A new day is a fresh start.
        </p>
        {filtered.length ? (
          <div className="routine-list">
            {filtered.map((s) => (
              <RoutineRow
                key={s.id}
                step={s}
                onToggle={() => onToggle(s.id)}
                onRemove={() => onRemove(s.id)}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Sprout size={40} strokeWidth={1.2} />
            <h3>Begin with one little ritual.</h3>
            <p>A product you use. A moment for yourself. It belongs here.</p>
          </div>
        )}
        <form className="add-routine" onSubmit={add}>
          <label className="field">
            Add a {period} step
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Apply my moisturizer"
              maxLength={100}
              required
            />
          </label>
          <button
            className="button primary"
            type="submit"
            disabled={!name.trim()}
          >
            <Plus size={17} /> Add step
          </button>
        </form>
      </section>
    </>
  );
}
function CheckInPage({
  cloud,
  existing,
  history,
  onSave,
}: {
  cloud: boolean;
  existing?: CheckIn;
  history: CheckIn[];
  onSave: (entry: CheckIn) => void;
}) {
  const [sleep, setSleep] = useState<number | null>(existing?.sleep ?? null);
  const [mood, setMood] = useState(existing?.mood ?? "");
  const [social, setSocial] = useState(existing?.social ?? "");
  const [note, setNote] = useState(existing?.note ?? "");
  useEffect(() => {
    setSleep(existing?.sleep ?? null);
    setMood(existing?.mood ?? "");
    setSocial(existing?.social ?? "");
    setNote(existing?.note ?? "");
  }, [existing]);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!mood || !social) return;
    onSave({ date: localDate(), sleep, mood, social, note: note.trim() });
  }
  return (
    <>
      <div className="page-intro">
        <span className="eyebrow">A PAUSE FOR THE WHOLE YOU</span>
        <h1>Come as you are.</h1>
        <p>No right answers. Just a little time to notice how you feel.</p>
      </div>
      <form className="checkin-form" onSubmit={submit}>
        <section className="panel checkin-section">
          <div className="question-icon lavender">
            <Moon size={23} />
          </div>
          <div>
            <h2>How did you sleep?</h2>
            <p>Think about last night, in your own time.</p>
            <label className="sleep-label" htmlFor="sleep-hours">
              <strong>{sleep === null ? "Not logged" : sleep}</strong>
              {sleep === null ? "" : " hours"}
            </label>
            <label className="consent">
              <input
                type="checkbox"
                checked={sleep !== null}
                onChange={(e) => setSleep(e.target.checked ? 7 : null)}
              />
              Include sleep hours in this check-in
            </label>
            <input
              disabled={sleep === null}
              id="sleep-hours"
              type="range"
              min="0"
              max="14"
              step="0.5"
              value={sleep ?? 7}
              onChange={(e) => setSleep(Number(e.target.value))}
            />
            <div className="range-labels">
              <span>0 hours</span>
              <span>14 hours</span>
            </div>
          </div>
        </section>
        <section className="panel checkin-section">
          <div className="question-icon sage">
            <Sun size={23} />
          </div>
          <div>
            <h2>How are you feeling?</h2>
            <p>However you feel today, there’s room for it.</p>
            <div
              className="choice-group"
              role="group"
              aria-label="Today's mood"
            >
              {["Low", "Okay", "Good", "Great"].map((value, i) => (
                <button
                  type="button"
                  aria-pressed={mood === value}
                  className={`choice ${mood === value ? "chosen" : ""}`}
                  onClick={() => setMood(value)}
                  key={value}
                >
                  <span className="mood-face">{["◡", "—", "⌣", "☺"][i]}</span>
                  {value}
                </button>
              ))}
            </div>
          </div>
        </section>
        <section className="panel checkin-section">
          <div className="question-icon peach">
            <Users size={23} />
          </div>
          <div>
            <h2>How connected do you feel?</h2>
            <p>A conversation, a shared moment, or time to yourself.</p>
            <div
              className="choice-group"
              role="group"
              aria-label="Today's connection"
            >
              {["Quiet time", "A little", "Connected"].map((value) => (
                <button
                  type="button"
                  aria-pressed={social === value}
                  className={`choice ${social === value ? "chosen" : ""}`}
                  onClick={() => setSocial(value)}
                  key={value}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
        </section>
        <section className="panel note-panel">
          <label className="field">
            Anything else on your mind?{" "}
            <span className="optional">Optional</span>
            <textarea
              value={note}
              maxLength={1000}
              onChange={(e) => setNote(e.target.value)}
              placeholder="A little reflection, just for you…"
              rows={3}
            />
          </label>
        </section>
        <div className="form-footer">
          <span>
            <ShieldCheck size={16} />{" "}
            {cloud ? "Saves to your account." : "Saves only in this browser."}
          </span>
          <button
            className="button primary"
            type="submit"
            disabled={!mood || !social}
          >
            {existing ? "Update today’s check-in" : "Save my check-in"}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
      {history.length > 0 && (
        <section className="history">
          <h2>Your moments of reflection</h2>
          {[...history]
            .sort((a, b) => b.date.localeCompare(a.date))
            .slice(0, 7)
            .map((entry) => (
              <article className="panel history-entry" key={entry.date}>
                <strong>{prettyDate(entry.date)}</strong>
                <span>
                  <Moon size={15} />
                  {entry.sleep === null
                    ? "Sleep not logged"
                    : `${entry.sleep}h sleep`}
                </span>
                <span>{entry.mood}</span>
                <span>{entry.social}</span>
                {entry.note && <p>{entry.note}</p>}
              </article>
            ))}
        </section>
      )}
    </>
  );
}
