from typing import Annotated
from fastapi import APIRouter, Request, Query
from src.errors import not_found
from .service import Category
router=APIRouter(prefix='/v1/products', tags=['products'])

@router.get('')
def products(request:Request, category:Category|None=None, q:Annotated[str,Query(max_length=100)]='', offset:Annotated[int,Query(ge=0)]=0, limit:Annotated[int,Query(ge=1,le=50)]=20):
    catalog=request.app.state.catalog
    rows=[p for p in catalog.products if (not category or p.category==category) and q.casefold() in (p.name+' '+p.brand).casefold()]
    rows.sort(key=lambda p:(p.brand.casefold(),p.name.casefold(),p.product_id))
    return {'items':[p.model_dump(mode='json') for p in rows[offset:offset+limit]],'total':len(rows),'catalog_version':catalog.version,
            'status':'ready' if rows else 'no_verified_products' if catalog.available else 'unavailable'}

@router.get('/{product_id}')
def product(product_id:str,request:Request):
    for row in request.app.state.catalog.products:
        if row.product_id==product_id:return row.model_dump(mode='json')
    raise not_found('Product')
