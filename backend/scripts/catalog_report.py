"""Report candidate verification gaps without publishing or modifying records."""
import json
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[2]
counts=Counter(); gaps=Counter()
for path in (root/'data/sources/candidates').glob('*.json'):
    for product in json.loads(path.read_text()):
        counts[product.get('verification_status','missing')]+=1
        for key in ('ingredient_list_raw','directions_raw','warnings_raw','verified_at'):
            if product.get(key) is None:gaps[key]+=1
        if not product.get('formulation_version',{}).get('version_id'):gaps['formulation_version.version_id']+=1
catalog=json.loads((root/'data/catalog/products.json').read_text())
audit_path=root/'data/catalog/verification-audit.json'
audit=json.loads(audit_path.read_text())['products'] if audit_path.is_file() else []
print(json.dumps({'candidate_status':dict(counts),'missing_fields_in_original_staging':dict(gaps),
                 'published_count':len(catalog['products']),
                 'published_ids':[p['product_id'] for p in catalog['products']],
                 'audit_status':dict(Counter(p['status'] for p in audit)),
                 'note':'Original candidate files remain staging snapshots. See verification-audit.json for review outcomes.'},indent=2))
