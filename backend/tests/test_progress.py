import io
import json
from uuid import uuid4
from PIL import Image


def photo_bytes():
    out = io.BytesIO()
    image = Image.new('RGB', (100, 120), '#ccaabb')
    exif = Image.Exif(); exif[270] = 'private metadata'
    image.save(out, 'JPEG', exif=exif)
    return out.getvalue()


def upload(actor, **changes):
    data = {'entry_id': str(uuid4()), 'captured_on': '2026-10-01', 'confirmed_real': True,
            'view': 'front', 'lighting': 'daylight', 'makeup': False, **changes}
    return actor.post('/v1/progress/photos', data={'metadata': json.dumps(data)},
                      files={'photo': ('test.jpg', photo_bytes(), 'image/jpeg')})


def report(**changes):
    return {'entry_id': str(uuid4()), 'product_id': 'rest_candidate_011', 'package_matches': True,
            'started_on': '2026-10-01', 'ended_on': '2026-10-03', 'used_days': 3,
            'helpfulness': 'no_change', 'irritation': 'none', **changes}


def test_usage_saved_snapshot_and_idempotency(alice, bob):
    values = report()
    result = alice.post('/v1/progress/usage', json=values)
    assert result.status_code == 200, result.text
    payload = result.json()['payload']
    assert payload['product_snapshot']['formulation_version']['version_id']
    assert payload['training_consent_at_collection'] is None
    assert payload['routine_snapshot'] == {'items': [], 'version': 0}
    assert alice.post('/v1/progress/usage', json=values).json() == result.json()
    assert alice.post('/v1/progress/usage', json={**values, 'helpfulness': 'helpful'}).status_code == 409
    assert bob.get('/v1/progress/usage').json()['items'] == []
    assert bob.delete('/v1/progress/' + values['entry_id']).status_code == 404
    assert len(alice.post('/v1/export').json()['usage_reports']) == 1
    alice.delete('/v1/account')
    assert alice.get('/v1/progress/usage').json()['items'] == []


def test_invalid_usage_is_rejected(alice):
    for values in ({'used_days': 4}, {'used_days': True}, {'used_days': 0}, {'ended_on': '2026-09-01'},
                   {'package_matches': False}, {'ended_on': '2099-01-01'}, {'owner': str(uuid4())}):
        assert alice.post('/v1/progress/usage', json=report(**values)).status_code == 422
    assert alice.post('/v1/progress/usage', json=report(product_id='unreviewed')).status_code == 404
    alice.delete('/v1/consents/service')
    assert alice.post('/v1/progress/usage', json=report()).status_code == 403


def test_private_photos_strip_metadata_and_revoke_purges(alice, bob):
    assert upload(alice).status_code == 403
    alice.consent('photo_storage'); bob.consent('photo_storage')
    saved = upload(alice)
    assert saved.status_code == 200, saved.text
    entry = saved.json()['id']
    image = alice.get(f'/v1/progress/photos/{entry}/image')
    assert image.headers['cache-control'] == 'no-store'
    with Image.open(io.BytesIO(image.content)) as decoded:
        assert not decoded.getexif()
    assert bob.get(f'/v1/progress/photos/{entry}/image').status_code == 404
    assert bob.get('/v1/progress/photos').json()['items'] == []
    alice.delete('/v1/consents/photo_storage')
    alice.consent('photo_storage')
    assert alice.get('/v1/progress/photos').json()['items'] == []
    assert alice.get(f'/v1/progress/photos/{entry}/image').status_code == 404


def test_comparison_order_capture_context_and_unvalidated_model(alice, bob):
    alice.consent('photo_storage'); bob.consent('photo_storage')
    before = upload(alice).json()['id']
    after = upload(alice, captured_on='2026-10-03', lighting='indoor').json()['id']
    alice.post('/v1/progress/usage', json=report())
    pair = {'before_id': before, 'after_id': after}
    comparison = alice.post('/v1/progress/comparisons', json=pair).json()
    assert comparison['capture_differences'] == ['lighting']
    assert not comparison['slider_allowed']
    assert len(comparison['usage_reports']) == 1
    assert bob.post('/v1/progress/comparisons', json=pair).status_code == 404
    assert alice.post('/v1/progress/comparisons', json={'before_id': after, 'after_id': before}).status_code == 422
    assert not alice.get('/v1/progress/model-readiness').json()['outcome_prediction_available']


def test_photo_idempotency_validation_and_limit(alice):
    alice.consent('photo_storage')
    identifier = str(uuid4())
    first = upload(alice, entry_id=identifier)
    assert upload(alice, entry_id=identifier).json() == first.json()
    assert upload(alice, entry_id=identifier, lighting='indoor').status_code == 409
    assert upload(alice, confirmed_real=False).status_code == 422
    assert upload(alice, captured_on='2099-01-01').status_code == 422
    assert alice.post('/v1/progress/photos', data={'metadata': '{}'}, files={'photo': ('bad.jpg', b'bad', 'image/jpeg')}).status_code == 422
    for _ in range(11): assert upload(alice).status_code == 200
    assert upload(alice).status_code == 409


def test_recommendation_feedback_links_to_actual_owned_suggestion(alice, bob):
    alice.patch('/v1/me', json={'skin_type': 'dry', 'ingredient_exclusions': []})
    shown = alice.post('/v1/recommendations', json={'category': 'moisturizer'}).json()
    values = {'entry_id': str(uuid4()), 'recommendation_id': shown['recommendation_id'],
              'product_id': shown['items'][0]['product']['product_id'], 'useful': True, 'reason': 'fits_preferences'}
    assert bob.post('/v1/progress/recommendation-feedback', json=values).status_code == 404
    assert alice.post('/v1/progress/recommendation-feedback', json={**values, 'product_id': 'unshown'}).status_code == 404
    result = alice.post('/v1/progress/recommendation-feedback', json=values)
    assert result.status_code == 200
    assert alice.post('/v1/progress/recommendation-feedback', json=values).json() == result.json()
    exported = alice.post('/v1/export').json()
    assert len(exported['recommendation_feedback']) == 1
    assert exported['recommendations'][0]['payload']['result']['rules_version']
