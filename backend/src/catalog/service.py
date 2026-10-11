"""Reviewed catalog only. Candidate staging files are deliberately never loaded."""
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, model_validator

Category = Literal['cleanser','moisturizer','serum','sunscreen','face_mask']

class Price(BaseModel):
    amount: float = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    package_size: dict
    checked_at: date
    source_url: HttpUrl
    @model_validator(mode='after')
    def package_known(self):
        value=self.package_size.get('value')
        if type(value) not in (int,float) or not 0 < value < 100000 or self.package_size.get('unit') not in {'ml','g','fl oz','oz','lb'}:
            raise ValueError('Price requires a known package size')
        return self

class GoalEvidence(BaseModel):
    goal: str = Field(min_length=1,max_length=100)
    statement: str = Field(min_length=1,max_length=500)
    source_url: HttpUrl
    review_status: Literal['reviewed']

class ProductImage(BaseModel):
    url: HttpUrl
    alt: str = Field(min_length=1, max_length=300)
    source_url: HttpUrl
    checked_at: date

    @model_validator(mode='after')
    def secure_image(self):
        if self.url.scheme != 'https' or self.source_url.scheme != 'https':
            raise ValueError('Product images and attribution must use HTTPS')
        return self

class Product(BaseModel):
    model_config = ConfigDict(extra='ignore')
    product_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    name: str = Field(min_length=1,max_length=200)
    brand: str = Field(min_length=1,max_length=200)
    market: str
    category: Category
    regulatory_class: Literal['cosmetic','otc_drug']
    formulation_version: dict
    ingredient_list_raw: str = Field(min_length=1)
    ingredients_normalized: list[str] = Field(min_length=1)
    directions_raw: str | None = Field(default=None, min_length=1)
    warnings_raw: str | None = None  # Empty only after verified absence; null means unknown.
    directions_summary: str | None = Field(default=None, min_length=1)
    warnings_summary: str | None = Field(default=None, min_length=1)
    review: dict = Field(default_factory=dict)
    verification_status: Literal['verified']
    verified_at: date
    source_url: HttpUrl
    texture: str | None = None
    price: Price | None = None
    image: ProductImage | None = None
    manufacturer_claims: dict = Field(default_factory=dict)
    compatibility_restrictions: list[dict] = Field(default_factory=list)
    goal_evidence: list[GoalEvidence] = Field(default_factory=list)
    @model_validator(mode='after')
    def formula_known(self):
        if not (self.directions_raw or self.directions_summary):
            raise ValueError('Reviewed directions are required')
        if self.warnings_raw is None and not self.warnings_summary:
            raise ValueError('Reviewed warnings or verified absence are required')
        if self.directions_summary or self.warnings_summary:
            if self.review.get('text_representation') != 'reviewed_summary':
                raise ValueError('Summarized instructions must be identified as reviewed summaries')
        if not self.formulation_version.get('version_id'):
            raise ValueError('A verified formulation version is required')
        if self.verified_at > date.today() or (self.price and self.price.checked_at > date.today()):
            raise ValueError('Verification dates cannot be in the future')
        if any(not ingredient.strip() for ingredient in self.ingredients_normalized):
            raise ValueError('Empty ingredient')
        return self

    @property
    def warning_text(self):
        return self.warnings_summary or self.warnings_raw or ''

class Catalog:
    def __init__(self, path=None):
        path=Path(path or os.getenv('REST_CATALOG_PATH', str(Path(__file__).resolve().parents[3]/'data/catalog/products.json')))
        # A missing mounted catalog is an explicit unavailable state, never candidate fallback.
        self.available=path.is_file()
        raw=path.read_bytes() if self.available else b'{"version":"unconfigured","products":[]}'
        payload=json.loads(raw)
        self.version=payload['version']+'-'+hashlib.sha256(raw).hexdigest()[:12]
        self.products=[Product.model_validate(p) for p in payload['products']]
        if len({p.product_id for p in self.products}) != len(self.products):
            raise ValueError('Duplicate catalog product IDs')
