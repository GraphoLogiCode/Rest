import { useEffect, useState } from "react";
import { accountApi, publicApi } from "../services/accountApi";
import { createLocalId, type RoutineStep } from "../services/storage";
type Product = {
  product_id: string;
  name: string;
  brand: string;
  category: string;
  ingredient_list_raw: string;
  directions_raw: string | null;
  warnings_raw: string | null;
  directions_summary?: string | null;
  warnings_summary?: string | null;
  source_url: string;
  verified_at: string;
  formulation_version: { version_id: string };
  price: null | {
    amount: number;
    currency: string;
    package_size: { value: number; unit: string };
  };
};
const categories = [
  ["cleanser", "Cleansers"],
  ["moisturizer", "Moisturizers"],
  ["serum", "Serums"],
  ["sunscreen", "Sunscreens"],
  ["face_mask", "Face masks"],
];
export function ProductCatalog({
  user,
  canSave,
  onAdd,
}: {
  user: string | null;
  canSave: boolean;
  onAdd: (step: RoutineStep) => Promise<boolean>;
}) {
  const [category, setCategory] = useState("moisturizer"),
    [query, setQuery] = useState("");
  const [items, setItems] = useState<Product[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [busy, setBusy] = useState(false);
  const [skin, setSkin] = useState(""),
    [exclusions, setExclusions] = useState(""),
    [none, setNone] = useState(false),
    [budget, setBudget] = useState(""),
    [currency, setCurrency] = useState("USD"),
    [goal, setGoal] = useState("");
  const [result, setResult] = useState<any>(null),
    [profileReady, setProfileReady] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError("");
    setItems([]);
    publicApi(
      `/v1/products?category=${category}&q=${encodeURIComponent(query)}&offset=${offset}`,
      ctrl.signal,
    )
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [category, query, offset]);
  useEffect(() => {
    const ctrl = new AbortController();
    setResult(null);
    setSkin("");
    setExclusions("");
    setNone(false);
    setBudget("");
    setProfileReady(false);
    if (user)
      void accountApi("/v1/me", { signal: ctrl.signal }, user)
        .then((p) => {
          if (ctrl.signal.aborted) return;
          setSkin(p.skin_type || "");
          setExclusions((p.ingredient_exclusions || []).join(", "));
          setNone(p.ingredient_exclusions?.length === 0);
          setBudget(p.budget?.amount?.toString() || "");
          setCurrency(p.budget?.currency || "USD");
          setProfileReady(true);
        })
        .catch((e) => {
          if (!ctrl.signal.aborted) setError(e.message);
        });
    return () => ctrl.abort();
  }, [user]);
  async function match() {
    if (!user || !canSave || !profileReady) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      await accountApi(
        "/v1/me",
        {
          method: "PATCH",
          body: JSON.stringify({
            skin_type: skin,
            ingredient_exclusions: exclusions.trim()
              ? exclusions
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean)
              : [],
            budget: budget === "" ? null : { amount: Number(budget), currency },
          }),
        },
        user,
      );
      const response = await accountApi(
        "/v1/recommendations",
        {
          method: "POST",
          body: JSON.stringify({
            category,
            ...(goal.trim() ? { goal: goal.trim() } : {}),
          }),
        },
        user,
      );
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not get suggestions.");
    } finally {
      setBusy(false);
    }
  }
  const [feedbackSaved, setFeedbackSaved] = useState<Record<string, string>>(
    {},
  );
  async function feedback(p: Product, useful: boolean) {
    if (!user || !result?.recommendation_id) return;
    setBusy(true);
    setError("");
    try {
      await accountApi(
        "/v1/progress/recommendation-feedback",
        {
          method: "POST",
          body: JSON.stringify({
            entry_id: createLocalId(),
            recommendation_id: result.recommendation_id,
            product_id: p.product_id,
            useful,
            reason: useful ? "fits_preferences" : "other",
          }),
        },
        user,
      );
      setFeedbackSaved((old) => ({
        ...old,
        [result.recommendation_id + p.product_id]:
          "Feedback saved. You can report actual use in your journal.",
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save feedback.");
    } finally {
      setBusy(false);
    }
  }
  function card(p: Product, reasons?: string[], cautions?: string[]) {
    return (
      <article
        className="panel"
        key={p.product_id}
        style={{ padding: 24, margin: "16px 0" }}
      >
        <span className="eyebrow">{p.brand}</span>
        <h3>{p.name}</h3>
        <p>
          {p.price
            ? `${p.price.currency} ${p.price.amount.toFixed(2)} · ${p.price.package_size.value} ${p.price.package_size.unit}`
            : "Package price not available"}
        </p>
        {reasons && (
          <ul>
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        {reasons && (
          <div>
            <p>Was this suggestion useful?</p>
            {feedbackSaved[result.recommendation_id + p.product_id] ? (
              <p role="status">
                {feedbackSaved[result.recommendation_id + p.product_id]}
              </p>
            ) : (
              <>
                <button
                  className="button secondary"
                  disabled={busy || !canSave}
                  onClick={() => void feedback(p, true)}
                >
                  Yes
                </button>
                <button
                  className="button secondary"
                  disabled={busy || !canSave}
                  onClick={() => void feedback(p, false)}
                >
                  No
                </button>
              </>
            )}
          </div>
        )}
        {cautions?.map((c) => (
          <p key={c}>{c}</p>
        ))}
        <details>
          <summary>Ingredients, directions and source</summary>
          <p>{p.ingredient_list_raw}</p>
          {p.directions_summary && (
            <p className="small-text">
              Directions and cautions summarized from the manufacturer. Check
              your package for the current label.
            </p>
          )}
          <p>{p.directions_summary || p.directions_raw}</p>
          <p>
            {p.warnings_summary ||
              p.warnings_raw ||
              "No label warning recorded during verification."}
          </p>
          <p>
            Source checked {p.verified_at}. Formulations may change; compare the
            ingredients on your package.
          </p>
          <a href={p.source_url} target="_blank" rel="noreferrer">
            Product source
          </a>
        </details>
        <button
          className="button secondary"
          disabled={!canSave || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onAdd({
                id: createLocalId(),
                name: p.name,
                period: "morning",
                product_id: p.product_id,
              });
            } finally {
              setBusy(false);
            }
          }}
        >
          Add to morning routine
        </button>
      </article>
    );
  }
  return (
    <>
      <div className="page-intro">
        <span className="eyebrow">PRODUCT CHOICES</span>
        <h1>Find a fit for your routine.</h1>
        <p>Reviewed product facts and transparent preference matching.</p>
      </div>
      <section className="panel" style={{ padding: 24 }}>
        <div className="form-row">
          <label className="field">
            Category
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setOffset(0);
                setResult(null);
              }}
            >
              {categories.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Search products
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setOffset(0);
              }}
            />
          </label>
        </div>
        {loading && <p role="status">Loading catalog…</p>}
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && !items.length && (
          <p>
            No verified products are available in this category yet. Products
            awaiting review are not displayed or recommended.
          </p>
        )}
        {items.map((p) => card(p))}
        {offset > 0 && (
          <button
            className="button secondary"
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Previous products
          </button>
        )}
        {offset + 20 < total && (
          <button
            className="button secondary"
            onClick={() => setOffset(offset + 20)}
          >
            More products
          </button>
        )}
      </section>
      <section className="panel" style={{ padding: 24, marginTop: 24 }}>
        <h2>Suggestions with reasons</h2>
        <p>
          The first version matches reviewed cleansers and moisturizers to
          explicit preferences. It does not predict results or use sleep, mood,
          stress, connection, or AI photos.
        </p>
        {!user && (
          <p>
            Sign in and enable account saving to save your preferences and
            request suggestions.
          </p>
        )}
        <fieldset
          className="account-fields"
          disabled={!canSave || !profileReady || busy}
          onChange={() => setResult(null)}
        >
          <label className="field">
            Skin type
            <select value={skin} onChange={(e) => setSkin(e.target.value)}>
              <option value="">Choose</option>
              {["dry", "normal", "combination", "oily"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Ingredients you avoid (comma separated)
            <input
              value={exclusions}
              onChange={(e) => {
                setExclusions(e.target.value);
                setNone(false);
              }}
              placeholder="Use ingredient names from labels"
            />
          </label>
          <label className="consent">
            <input
              type="checkbox"
              checked={none}
              onChange={(e) => {
                setNone(e.target.checked);
                if (e.target.checked) setExclusions("");
              }}
            />
            I have no ingredient exclusions to report.
          </label>
          <div className="form-row">
            <label className="field">
              Maximum package price (optional)
              <input
                type="number"
                min="0"
                step="0.01"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </label>
            <label className="field">
              Currency
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
              >
                {[...new Set(["USD", "CAD", "GBP", "EUR", currency])].map(
                  (c) => (
                    <option key={c}>{c}</option>
                  ),
                )}
              </select>
            </label>
          </div>
          <label className="field">
            Goal (optional)
            <input
              maxLength={100}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Only goals with reviewed evidence can match"
            />
          </label>
          <button
            className="button primary"
            disabled={!skin || (!none && !exclusions.trim())}
            onClick={() => void match()}
          >
            Save preferences and find suggestions
          </button>
        </fieldset>
        {busy && <p role="status">Saving…</p>}
        {result && (
          <div aria-live="polite">
            <p>
              {result.status === "ready"
                ? "Matches to your stated preferences"
                : result.status === "catalog_unavailable"
                  ? "The reviewed catalog is not configured yet."
                  : result.status === "no_verified_products"
                    ? "No verified products are available yet."
                    : result.status === "needs_ingredient_review"
                      ? "An exclusion needs ingredient review. No products were recommended."
                      : result.status === "needs_profile"
                        ? "Complete your skin type and ingredient exclusions first."
                        : "No verified products meet these constraints. We have not relaxed your preferences."}
            </p>
            {result.items.map((r: any) =>
              card(r.product, r.reasons, r.cautions),
            )}
            <p className="small-text">
              {result.limitations.join(" ")} Rules: {result.rules_version}.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
