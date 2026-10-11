import { useEffect, useState } from 'react';
import { publicApi } from '../services/accountApi';

export type PreviewProduct = {
  product_id: string;
  brand: string;
  name: string;
  category: string;
  source_url: string;
  image?: { url: string; alt: string; source_url: string; checked_at: string } | null;
  price: { amount: number; currency: string; package_size: { value: number; unit: string } } | null;
};

export function PreviewProductPicker({ value, onChange, disabled }: {
  value: PreviewProduct | null;
  onChange: (product: PreviewProduct | null) => void;
  disabled: boolean;
}) {
  const [items, setItems] = useState<PreviewProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true); setError('');
    // Read all pages so the selector does not silently omit catalog products.
    void (async () => {
      const products: PreviewProduct[] = [];
      let offset = 0;
      while (true) {
        const page = await publicApi(`/v1/products?limit=50&offset=${offset}`, ctrl.signal);
        products.push(...page.items);
        offset += page.items.length;
        if (!page.items.length || offset >= page.total) break;
      }
      if (!ctrl.signal.aborted) setItems(products);
    })().catch(() => {
      if (!ctrl.signal.aborted) setError('Products could not load. You can still create an illustration without one.');
    }).finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [attempt]);
  return <div className="preview-product-picker">
    <label className="field">Product to show beside your preview
      <select value={value?.product_id || ''} disabled={disabled || loading}
        onChange={e => onChange(items.find(item => item.product_id === e.target.value) || null)}>
        <option value="">{loading ? 'Loading products…' : 'No product selected'}</option>
        {items.map(item => <option key={item.product_id} value={item.product_id}>{item.brand} · {item.name}</option>)}
      </select>
    </label>
    {value && <PreviewProductImage key={value.image?.url || value.product_id} product={value} compact />}
    <p className="small-text">The product card accompanies the illustration. Product selection does not change the generated skin appearance.</p>
    {error && <p role="alert">{error} <button type="button" className="button secondary" disabled={disabled} onClick={() => setAttempt(n => n + 1)}>Retry products</button></p>}
  </div>;
}

function PreviewProductImage({ product, compact = false }: { product: PreviewProduct; compact?: boolean }) {
  const [failed, setFailed] = useState(false);
  const [image, setImage] = useState(product.image);
  useEffect(() => {
    // Existing job snapshots may predate the catalog's image metadata.
    if (product.image) { setImage(product.image); return; }
    const ctrl = new AbortController();
    void publicApi(`/v1/products/${encodeURIComponent(product.product_id)}`, ctrl.signal)
      .then(value => { if (!ctrl.signal.aborted) setImage(value.image); })
      .catch(() => {});
    return () => ctrl.abort();
  }, [product.product_id, product.image]);
  return <div className={`preview-product-image${compact ? ' compact' : ''}`}>
    {image && !failed
      ? <img src={image.url} alt={image.alt} width="320" height="320"
          referrerPolicy="no-referrer" decoding="async" onError={() => setFailed(true)} />
      : <p className="small-text">Product photo unavailable. View product details below.</p>}
  </div>;
}

export function PreviewProductCard({ product }: { product: PreviewProduct }) {
  return <aside className="preview-product-card" aria-label="Product beside AI preview">
    <span className="small-text">SELECTED PRODUCT</span>
    <PreviewProductImage key={product.image?.url || product.product_id} product={product} />
    <p className="preview-product-brand">{product.brand}</p>
    <h3>{product.name}</h3>
    <p>{product.category.replace(/_/g, ' ')}</p>
    {product.price && <p>{product.price.currency} {product.price.amount.toFixed(2)} · {product.price.package_size.value} {product.price.package_size.unit}</p>}
    <a href={product.source_url} target="_blank" rel="noopener noreferrer">View product details ↗</a>
    <p className="small-text">Shown for reference. The AI image is not a demonstration of this product’s effects.</p>
  </aside>;
}
