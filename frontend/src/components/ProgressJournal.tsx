import { useEffect, useRef, useState, type FormEvent } from "react";
import { accountApi, accountPhoto, publicApi } from "../services/accountApi";
import { createLocalId, localDate } from "../services/storage";
type Entry = { id: string; payload: Record<string, any> };
type Product = { product_id: string; name: string; brand: string };

function SavedPhoto({ entry, user }: { entry: Entry; user: string }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const ctrl = new AbortController();
    let objectUrl = "";
    accountPhoto(entry.id, ctrl.signal, user)
      .then((blob) => {
        if (ctrl.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      });
    return () => {
      ctrl.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [entry.id, user]);
  return (
    <figure style={{ margin: 0 }}>
      {url && (
        <>
          <img
            style={{ width: "100%", maxHeight: 500, objectFit: "contain" }}
            src={url}
            alt={`Your photo from ${entry.payload.captured_on}`}
          />
          <a href={url} download={`rest-${entry.payload.captured_on}.jpg`}>
            Download photo
          </a>
        </>
      )}
      <figcaption>
        {entry.payload.captured_on} · {entry.payload.view} ·{" "}
        {entry.payload.lighting}
      </figcaption>
      {error && <p role="alert">{error}</p>}
    </figure>
  );
}

export function ProgressJournal({
  user,
  canSave,
}: {
  user: string | null;
  canSave: boolean;
}) {
  const [products, setProducts] = useState<Product[]>([]),
    [usage, setUsage] = useState<Entry[]>([]),
    [photos, setPhotos] = useState<Entry[]>([]);
  const [photoConsent, setPhotoConsent] = useState(false),
    [training, setTraining] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [before, setBefore] = useState(""),
    [after, setAfter] = useState(""),
    [comparison, setComparison] = useState<any>(null);
  const life = useRef(new AbortController());
  const api = (path: string, init: RequestInit = {}) =>
    accountApi(
      path,
      { ...init, signal: life.current.signal },
      user || undefined,
    );
  async function refresh() {
    const [consents, reports] = await Promise.all([
      api("/v1/consents"),
      api("/v1/progress/usage"),
    ]);
    if (life.current.signal.aborted) return;
    const active = consents.items
      .filter((c: any) => c.active)
      .map((c: any) => c.consent_type);
    const enabled = active.includes("photo_storage");
    setPhotoConsent(enabled);
    if (!enabled) setComparison(null);
    setTraining(active.includes("model_training"));
    setUsage(reports.items);
    const saved = enabled ? await api("/v1/progress/photos") : { items: [] };
    if (!life.current.signal.aborted) setPhotos(saved.items);
  }
  useEffect(() => {
    life.current = new AbortController();
    const ctrl = life.current;
    publicApi("/v1/products?limit=50", ctrl.signal)
      .then((r) => {
        if (!ctrl.signal.aborted) setProducts(r.items);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      });
    if (user)
      refresh().catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      });
    return () => ctrl.abort();
  }, [user, canSave]);
  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      if (!life.current.signal.aborted)
        setError(e instanceof Error ? e.message : "Could not save.");
    } finally {
      if (!life.current.signal.aborted) setBusy(false);
    }
  }
  async function consent(kind: string, enabled: boolean) {
    await api(
      `/v1/consents/${kind}`,
      enabled
        ? {
            method: "PUT",
            body: JSON.stringify({ version: "progress-2026-10-11" }),
          }
        : { method: "DELETE" },
    );
    if (kind === "photo_storage" && !enabled) {
      setComparison(null);
      setBefore("");
      setAfter("");
      setPhotos([]);
    }
    await refresh();
  }
  function productOptions(optional = false) {
    return (
      <>
        <option value="">
          {optional ? "No product link" : "Choose a reviewed product"}
        </option>
        {products.map((p) => (
          <option key={p.product_id} value={p.product_id}>
            {p.brand} · {p.name}
          </option>
        ))}
      </>
    );
  }
  function saveUsage(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    void run(async () => {
      await api("/v1/progress/usage", {
        method: "POST",
        body: JSON.stringify({
          entry_id: createLocalId(),
          product_id: f.get("product"),
          package_matches: true,
          started_on: f.get("start"),
          ended_on: f.get("end"),
          used_days: Number(f.get("days")),
          helpfulness: f.get("helpfulness"),
          irritation: f.get("irritation"),
          stopped: f.get("stopped") === "on",
          routine_changes: f.get("changes"),
        }),
      });
      form.reset();
      await refresh();
      setNotice("Product-use feedback saved.");
    });
  }
  function savePhoto(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const file = f.get("photo") as File;
    if (file.size > 10 * 1024 * 1024) {
      setError("Choose a photo under 10 MB and at most 4 megapixels.");
      return;
    }
    const body = new FormData();
    body.set("photo", file);
    body.set(
      "metadata",
      JSON.stringify({
        entry_id: createLocalId(),
        captured_on: f.get("date"),
        confirmed_real: f.get("real") === "on",
        view: f.get("view"),
        lighting: f.get("lighting"),
        makeup:
          f.get("makeup") === "unknown" ? null : f.get("makeup") === "yes",
        product_id: f.get("product") || null,
      }),
    );
    void run(async () => {
      await api("/v1/progress/photos", { method: "POST", body });
      form.reset();
      await refresh();
      setNotice("Real photo saved privately to your account.");
    });
  }
  return (
    <div className="panel progress-journal" style={{ padding: 24 }}>
      <h2>Your observed progress</h2>
      <p>
        Save real photos and record what you actually used. These observations
        cannot determine which product or lifestyle change caused a difference.
      </p>
      {!user && (
        <p>
          Sign in under Settings & privacy to save progress. The other tab
          offers a temporary comparison on this device.
        </p>
      )}
      {user && !canSave && (
        <p>Enable account saving under Settings & privacy to add records.</p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <fieldset disabled={!user || !canSave || busy} className="account-fields">
        <label className="consent">
          <input
            type="checkbox"
            checked={photoConsent}
            onChange={(e) =>
              void run(() => consent("photo_storage", e.target.checked))
            }
          />
          Save my photos privately. Turning this off deletes my saved photos
          from active storage.
        </label>
        <label className="consent">
          <input
            type="checkbox"
            checked={training}
            onChange={(e) =>
              void run(() => consent("model_training", e.target.checked))
            }
          />
          Separately allow my records to be considered for future model
          training. Optional; training is not running. I can withdraw this
          permission.
        </label>
      </fieldset>
      <form onSubmit={saveUsage}>
        <h3>Product-use feedback</h3>
        <p>
          Report your own experience, including no change. The saved record
          includes the catalog formulation and your current routine; confirm the
          package matches.
        </p>
        <fieldset className="account-fields" disabled={!canSave || busy}>
          <label className="field">
            Product
            <select name="product" required>
              {productOptions()}
            </select>
          </label>
          <div className="form-row">
            <label className="field">
              Started
              <input name="start" type="date" required max={localDate()} />
            </label>
            <label className="field">
              Through
              <input
                name="end"
                type="date"
                required
                defaultValue={localDate()}
                max={localDate()}
              />
            </label>
            <label className="field">
              Days actually used
              <input
                name="days"
                type="number"
                required
                min="0"
                max="3650"
                step="1"
              />
            </label>
          </div>
          <label className="field">
            Reported helpfulness
            <select name="helpfulness">
              <option value="unknown">Not sure / not used</option>
              <option value="helpful">Helpful</option>
              <option value="no_change">No change</option>
              <option value="unhelpful">Unhelpful</option>
            </select>
          </label>
          <label className="field">
            Reported irritation
            <select name="irritation">
              <option value="unknown">Not sure / not used</option>
              {["none", "mild", "moderate", "severe"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="consent">
            <input name="stopped" type="checkbox" />I stopped using this
            product.
          </label>
          <label className="field">
            Other routine changes (optional)
            <textarea name="changes" maxLength={1000} />
          </label>
          <label className="consent">
            <input type="checkbox" required />I checked that my package matches
            the listed product and ingredients.
          </label>
          <button className="button primary">Save use report</button>
        </fieldset>
      </form>
      <form onSubmit={savePhoto}>
        <h3>Save a real photo</h3>
        <p>
          Use the same light, distance, angle and expression each time. Avoid
          filters. JPG, PNG or WebP, up to 10 MB and 4 megapixels. Photos are
          resized and metadata removed; skin appearance is not edited. Pilot
          limit: 12 saved photos.
        </p>
        <fieldset
          className="account-fields"
          disabled={!canSave || !photoConsent || busy}
        >
          <label className="field">
            Photo
            <input
              name="photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              required
            />
          </label>
          <label className="field">
            Captured on
            <input
              name="date"
              type="date"
              required
              max={localDate()}
              defaultValue={localDate()}
            />
          </label>
          <div className="form-row">
            <label className="field">
              View
              <select name="view">
                {["front", "left", "right"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Lighting
              <select name="lighting">
                {["unknown", "daylight", "indoor", "mixed"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Makeup
              <select name="makeup">
                <option value="unknown">Not recorded</option>
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </label>
          </div>
          <label className="field">
            Related product (optional)
            <select name="product">{productOptions(true)}</select>
          </label>
          <label className="consent">
            <input name="real" type="checkbox" required />
            This is my real, unfiltered photo, not a generated or retouched
            result.
          </label>
          <button className="button primary">Save photo</button>
        </fieldset>
      </form>
      {user && photos.length > 0 && (
        <section>
          <h3>Compare dated photos</h3>
          <div className="form-row">
            {[
              ["Before", before, setBefore],
              ["After", after, setAfter],
            ].map(([label, value, setter]: any) => (
              <label className="field" key={label}>
                {label}
                <select
                  value={value}
                  onChange={(e) => {
                    setter(e.target.value);
                    setComparison(null);
                  }}
                >
                  <option value="">Choose a photo</option>
                  {photos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.payload.captured_on} · {p.payload.view} ·{" "}
                      {p.id.slice(0, 6)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <button
            className="button secondary"
            disabled={!before || !after || busy}
            onClick={() =>
              void run(async () =>
                setComparison(
                  await api("/v1/progress/comparisons", {
                    method: "POST",
                    body: JSON.stringify({
                      before_id: before,
                      after_id: after,
                    }),
                  }),
                ),
              )
            }
          >
            Compare
          </button>
          {comparison && (
            <>
              <div className="photo-grid">
                <SavedPhoto entry={comparison.before} user={user} />
                <SavedPhoto entry={comparison.after} user={user} />
              </div>
              <p>{comparison.interpretation}</p>
              <p>
                {comparison.capture_differences.length
                  ? `Capture details differ or are missing: ${comparison.capture_differences.join(", ")}. Interpret visual differences cautiously.`
                  : "Recorded capture details match; lighting and positioning can still differ."}
              </p>
              <p>
                {comparison.usage_reports.length} product-use reports overlap
                this period.
              </p>
            </>
          )}
          <details>
            <summary>Manage saved photos ({photos.length})</summary>
            {photos.map((p) => (
              <p key={p.id}>
                {p.payload.captured_on} · {p.payload.view}{" "}
                <button
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await api(`/v1/progress/${p.id}`, { method: "DELETE" });
                      setComparison(null);
                      await refresh();
                    })
                  }
                >
                  Delete photo
                </button>
              </p>
            ))}
          </details>
        </section>
      )}
      {usage.length > 0 && (
        <details>
          <summary>Your saved use reports ({usage.length})</summary>
          {usage.map((r) => (
            <p key={r.id}>
              {r.payload.product_snapshot.name} · {r.payload.started_on}–
              {r.payload.ended_on} · {r.payload.used_days} days ·{" "}
              {r.payload.helpfulness} · irritation: {r.payload.irritation}{" "}
              <button
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await api(`/v1/progress/${r.id}`, { method: "DELETE" });
                    setComparison(null);
                    await refresh();
                  })
                }
              >
                Delete report
              </button>
            </p>
          ))}
        </details>
      )}
      <h3>Data-based outcome preview</h3>
      <p>
        Not available yet. Rest has no validated model that predicts how a
        product will change your face. Saved observations will support
        evaluation only with separate training permission. This view uses your
        actual photos and does not generate an “after.”
      </p>
    </div>
  );
}
