"""Versioned, deterministic preference matching; never an efficacy prediction."""
from datetime import date
import unicodedata
RULE_VERSION='preferences.v2'
# Small explicit alias map, not substring or fuzzy allergy matching.
ALIASES={'aqua':'water','eau':'water','aqua / water / eau':'water',
         'aqua (water)':'water','water (aqua / eau)':'water','water (aqua/eau)':'water',
         'water/aqua/eau':'water','water / aqua / eau':'water','parfum':'fragrance'}
def canonical(value):
    text=' '.join(unicodedata.normalize('NFKC',value).casefold().split())
    return ALIASES.get(text,text)

def recommend(catalog, profile, category, goal=None, texture=None):
    missing=[]
    if not profile.skin_type:missing.append('skin_type')
    if profile.ingredient_exclusions is None:missing.append('ingredient_exclusions')
    base={'rules_version':RULE_VERSION,'catalog_version':catalog.version,'items':[], 'missing_information':missing,
          'limitations':['Preference matching is not a prediction of results or a guarantee of tolerance.',
                         'Sleep, mood, stress, social connection and generated photos are not ranking inputs.']}
    if missing:return {**base,'status':'needs_profile'}
    if not catalog.available:return {**base,'status':'catalog_unavailable'}
    if not catalog.products:return {**base,'status':'no_verified_products'}
    known={canonical(i) for p in catalog.products for i in p.ingredients_normalized}
    exclusions={canonical(i) for i in profile.ingredient_exclusions}
    if exclusions-known:
        return {**base,'status':'needs_ingredient_review','missing_information':['recognized_ingredient_exclusions']}
    results=[]; excluded={}
    def skip(reason):excluded[reason]=excluded.get(reason,0)+1
    for p in catalog.products:
        if p.category!=category:continue
        if p.category not in {'cleanser','moisturizer'} or p.regulatory_class!='cosmetic':skip('outside_pilot');continue
        if exclusions & {canonical(i) for i in p.ingredients_normalized}:skip('ingredient_exclusion');continue
        # Do not invent compatibility rules from prose cautions.
        if p.compatibility_restrictions:skip('requires_label_review');continue
        marketed=p.manufacturer_claims.get('skin_types',[])
        if profile.skin_type not in marketed:skip('skin_type_not_documented');continue
        if texture and p.texture!=texture:skip('texture_not_matched');continue
        evidence=next((e for e in p.goal_evidence if canonical(e.goal)==canonical(goal)),None) if goal else None
        if goal and not evidence:skip('goal_evidence_missing');continue
        reasons=[f'In your requested category: {category}.',f'Manufacturer lists {profile.skin_type} skin; this is a label claim.']
        if texture:reasons.append(f'Matches your requested texture: {texture}.')
        if evidence:reasons.append(evidence.statement)
        if profile.budget_amount is not None:
            if not p.price or p.price.currency!=profile.budget_currency or (date.today()-p.price.checked_at).days>90:
                skip('comparable_current_price_missing');continue
            if p.price.amount>float(profile.budget_amount):skip('over_budget');continue
            reasons.append('Listed package price is within your saved budget; tax and shipping are not included.')
        results.append({'product':p.model_dump(mode='json'),'reasons':reasons,
                        'evidence_sources':[str(evidence.source_url)] if evidence else [],'cautions':[p.warning_text] if p.warning_text else [],
                        'ingredient_screen':'No exact match to the reported exclusions in the reviewed ingredient list; not a safety clearance.'})
    results.sort(key=lambda row:row['product']['product_id'])
    return {**base,'status':'ready' if results else 'no_eligible_products','items':results[:5],'excluded_counts':excluded,
            'ordering':'All results satisfy the same explicit constraints; ties use stable product ID.'}
