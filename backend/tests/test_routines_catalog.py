from copy import deepcopy
from datetime import date
import json
from uuid import uuid4
import pytest
from src.catalog.service import Catalog
from src.recommendations.engine import recommend
from src.storage.memory import MemoryStore


def test_routine_saved_owned_conflict_and_export(alice,bob):
    item={'id':uuid4().hex,'name':'My moisturizer','period':'morning','completedOn':date.today().isoformat()}
    first=alice.put('/v1/routine',json={'version':0,'items':[item]})
    assert first.status_code==200,first.text
    assert first.json()['version']==1
    assert bob.get('/v1/routine').json()=={'version':0,'items':[]}
    assert alice.put('/v1/routine',json={'version':0,'items':[]}).status_code==409
    assert alice.get('/v1/routine').json()['items'][0]['name']=='My moisturizer'
    assert alice.post('/v1/export').json()['routine']['items'][0]['id']==item['id']
    assert alice.put('/v1/routine',json={'version':1,'items':[item,item]}).status_code==422
    assert alice.delete('/v1/account').json()['deleted']['routine_state']==1
    assert alice.get('/v1/routine').json()=={'version':0,'items':[]}


def test_routine_write_requires_consent_and_ignores_no_owner_override(client,new_user):
    from tests.conftest import Actor
    actor=Actor(client,new_user())
    assert actor.put('/v1/routine',json={'version':0,'items':[]}).status_code==403
    actor.consent()
    assert actor.put('/v1/routine',json={'version':0,'items':[],'user_id':str(uuid4())}).status_code==422


def product(**changes):
    row={'product_id':'test_only_1','name':'Synthetic fixture','brand':'Test brand','category':'moisturizer','market':'US',
        'regulatory_class':'cosmetic','formulation_version':{'version_id':'test-v1'},'ingredient_list_raw':'Water, Glycerin',
        'ingredients_normalized':['water','glycerin'],'directions_raw':'Fixture directions','warnings_raw':'Fixture warning',
        'verification_status':'verified','verified_at':date.today().isoformat(),'source_url':'https://example.com/test-only',
        'manufacturer_claims':{'skin_types':['dry'],'benefits':['Marketing does not prove a goal']},
        'price':{'amount':10,'currency':'USD','package_size':{'value':50,'unit':'ml'},'checked_at':date.today().isoformat(),'source_url':'https://example.com/test-only'}}
    return {**row,**changes}

def catalog(tmp_path,rows):
    path=tmp_path/'catalog.json';path.write_text(json.dumps({'version':'test-only','products':rows}));return Catalog(path)

def profile():
    store=MemoryStore()
    return store.update_profile(uuid4(),{'skin_type':'dry','ingredient_exclusions':[]})

def test_catalog_refuses_staged_or_unversioned_records(tmp_path):
    for changes in ({'verification_status':'pending'},{'formulation_version':{}},{'ingredients_normalized':[]}):
        with pytest.raises(ValueError):catalog(tmp_path,[product(**changes)])

def test_rules_hard_constraints_and_missing_data(tmp_path):
    c=catalog(tmp_path,[product()]);p=profile()
    assert recommend(c,p,'moisturizer')['items'][0]['product']['product_id']=='test_only_1'
    p.ingredient_exclusions=['AQUA']
    assert recommend(c,p,'moisturizer')['items']==[]
    p.ingredient_exclusions=['unrecognized allergy group']
    assert recommend(c,p,'moisturizer')['status']=='needs_ingredient_review'
    p.ingredient_exclusions=None
    assert recommend(c,p,'moisturizer')['status']=='needs_profile'
    p.ingredient_exclusions=[];p.budget_amount=5;p.budget_currency='USD'
    assert recommend(c,p,'moisturizer')['excluded_counts']=={'over_budget':1}
    p.budget_amount=15;p.budget_currency='EUR'
    assert recommend(c,p,'moisturizer')['items']==[]


def test_rules_no_marketing_or_lifestyle_inference_and_stable_order(tmp_path):
    c=catalog(tmp_path,[product(product_id='z'),product(product_id='a')]);p=profile()
    assert [r['product']['product_id'] for r in recommend(c,p,'moisturizer')['items']]==['a','z']
    assert recommend(c,p,'moisturizer',goal='Marketing does not prove a goal')['items']==[]
    p.goals=['Sleep better'];p.concerns=['stress']
    assert [r['product']['product_id'] for r in recommend(c,p,'moisturizer')['items']]==['a','z']


def test_public_catalog_only_publishes_reviewed_subset_and_uses_own_profile(alice,bob):
    published=alice.get('/v1/products').json()['items']
    assert {p['product_id'] for p in published}=={f'rest_candidate_{n:03}' for n in (2,3,5,11,12,13,15,16,25)}
    assert alice.get('/v1/products/rest_candidate_007').status_code==404
    assert alice.post('/v1/recommendations',json={'category':'moisturizer','user_id':str(bob.id)}).status_code==422
    assert alice.post('/v1/recommendations',json={'category':'moisturizer'}).json()['status']=='needs_profile'
    assert alice.patch('/v1/me',json={'skin_type':'oily','ingredient_exclusions':[]}).status_code==200
    matched=alice.post('/v1/recommendations',json={'category':'moisturizer'}).json()
    assert matched['status']=='ready'
    assert len(matched['items'])==2
    assert all(r['cautions'] and r['product']['directions_summary'] for r in matched['items'])
    assert bob.post('/v1/recommendations',json={'category':'moisturizer'}).json()['status']=='needs_profile'
    alice.patch('/v1/me',json={'ingredient_exclusions':['AQUA']})
    assert alice.post('/v1/recommendations',json={'category':'moisturizer'}).json()['items']==[]


def test_unknown_warnings_and_unreviewed_summaries_cannot_be_published(tmp_path):
    for changes in ({'warnings_raw':None}, {'directions_raw':None},
                    {'warnings_raw':None,'warnings_summary':'Unreviewed text'},
                    {'warnings_raw':None,'warnings_summary':''}):
        with pytest.raises(ValueError):catalog(tmp_path,[product(**changes)])


def test_new_catalog_water_aliases_never_bypass_exclusions(tmp_path):
    for water in ('Aqua (Water)','Water (Aqua / Eau)','Water (Aqua/Eau)'):
        c=catalog(tmp_path,[product(ingredients_normalized=[water,'glycerin'])])
        p=profile();p.ingredient_exclusions=['water']
        assert recommend(c,p,'moisturizer')['excluded_counts']=={'ingredient_exclusion':1}


def test_empty_reviewed_catalog_does_not_load_candidates(tmp_path):
    c=catalog(tmp_path,[])
    assert recommend(c,profile(),'moisturizer')['status']=='no_verified_products'
