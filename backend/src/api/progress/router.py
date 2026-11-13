"""Observed product use and real photos; no generated treatment outcome claims."""
import hashlib
import io
import json
import warnings
from uuid import UUID

from fastapi import APIRouter, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from src.visualization.router import upload_form

from src.auth import CurrentUser
from src.errors import ApiError, not_found
from src.privacy.consent import require_consent
from src.storage import StoreDep
from src.visualization.client import owner_lock
from .schemas import UsageReport, PhotoRecord, Comparison, RecommendationFeedback

router = APIRouter(prefix='/v1/progress', tags=['progress'])
MAX_UPLOAD = 10 * 1024 * 1024


def selected_product(request, product_id):
    if product_id is None:
        return None
    for product in request.app.state.catalog.products:
        if product.product_id == product_id:
            return product.model_dump(mode='json')
    raise not_found('Reviewed product')


def saved_payload(store, user_id, values, product):
    consent = store.active_consent(user_id, 'model_training')
    return {**values, 'product_snapshot': product, 'routine_snapshot': store.get_routine(user_id),
            'training_consent_at_collection': str(consent.id) if consent else None,
            'schema_version': 'progress.v1'}


def fingerprint(values, image=b''):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode() + image).hexdigest()


@router.post('/usage', dependencies=[require_consent('service')])
async def report_usage(body: UsageReport, request: Request, user: CurrentUser, store: StoreDep):
    product = selected_product(request, body.product_id)
    values = body.model_dump(mode='json', exclude={'entry_id'})
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, 'service'):
            raise ApiError(403, 'consent_required', 'Account saving must be enabled.')
        return store.create_progress(user.id, body.entry_id, 'usage',
            saved_payload(store, user.id, values, product), fingerprint(values))


@router.get('/usage')
def usage_history(user: CurrentUser, store: StoreDep):
    return {'items': store.list_progress(user.id, 'usage')}


def normalize_photo(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('Choose one JPG, PNG or WebP photo')
                if source.width * source.height > 4_000_000 or min(source.size) < 64:
                    raise ValueError('Photo must be at least 64 pixels per side and at most 4 megapixels')
                photo = ImageOps.exif_transpose(source).convert('RGB')
                photo.thumbnail((1280, 1280))
                output = io.BytesIO()
                # Do not copy EXIF, GPS or other uploaded metadata. No cosmetic edits.
                photo.save(output, 'JPEG', quality=90)
                encoded = output.getvalue()
                if len(encoded) > 2 * 1024 * 1024:
                    raise ValueError('Compressed photo is too large')
                return encoded, {'width': photo.width, 'height': photo.height,
                                 'processing': 'EXIF orientation, resize to max 1280px, JPEG compression; no cosmetic edits'}
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ApiError(422, 'invalid_photo', 'Choose a single JPG, PNG or WebP, 64 pixels per side to 4 megapixels.') from exc


@router.post('/photos', dependencies=[require_consent('service'), require_consent('photo_storage')])
async def save_photo(request: Request, user: CurrentUser, store: StoreDep):
    # Authenticate and check consents before reading a bounded multipart body.
    async with await upload_form(request) as form:
        if set(form) != {'metadata', 'photo'} or len(form.multi_items()) != 2:
            raise ApiError(422, 'invalid_upload', 'Provide one photo and its capture details.')
        metadata, photo = form['metadata'], form['photo']
        if not isinstance(metadata, str) or len(metadata) > 2000 or not isinstance(photo, UploadFile):
            raise ApiError(422, 'invalid_upload', 'Provide one photo and its capture details.')
        try:
            body = PhotoRecord.model_validate_json(metadata)
        except ValidationError as exc:
            raise ApiError(422, 'invalid_photo_metadata', 'Provide a real-photo confirmation, date and capture details.') from exc
        product = selected_product(request, body.product_id)
        raw = await photo.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise ApiError(413, 'photo_too_large', 'Photo must be under 10 MB.')
    encoded, details = await run_in_threadpool(normalize_photo, raw)
    values = body.model_dump(mode='json', exclude={'entry_id'})
    async with owner_lock(user.id, store):
        # Recheck after decoding so concurrent revocation cannot repopulate storage.
        if not store.active_consent(user.id, 'photo_storage') or not store.active_consent(user.id, 'service'):
            raise ApiError(403, 'consent_required', 'Photo storage and account saving must be enabled.')
        payload = saved_payload(store, user.id, {**values, **details}, product)
        return store.create_progress(user.id, body.entry_id, 'photo', payload, fingerprint(values, raw), encoded)


@router.get('/photos', dependencies=[require_consent('photo_storage')])
def photo_history(user: CurrentUser, store: StoreDep):
    return {'items': store.list_progress(user.id, 'photo')}


@router.get('/photos/{photo_id}/image', dependencies=[require_consent('photo_storage')])
def photo_image(photo_id: UUID, user: CurrentUser, store: StoreDep):
    image = store.progress_image(user.id, photo_id)
    if image is None:
        raise not_found('Photo')
    return Response(image, media_type='image/jpeg', headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.delete('/{entry_id}', status_code=204)
async def remove_entry(entry_id: UUID, user: CurrentUser, store: StoreDep):
    async with owner_lock(user.id, store):
        if not store.delete_progress(user.id, entry_id):
            raise not_found('Progress record')
    return Response(status_code=204)


@router.post('/comparisons', dependencies=[require_consent('photo_storage')])
def compare(body: Comparison, user: CurrentUser, store: StoreDep):
    photos = {r['id']: r for r in store.list_progress(user.id, 'photo')}
    before, after = photos.get(str(body.before_id)), photos.get(str(body.after_id))
    if before is None or after is None:
        raise not_found('Photo')
    b, a = before['payload'], after['payload']
    if a['captured_on'] <= b['captured_on']:
        raise ApiError(422, 'photo_order', 'Choose an after photo dated later than the before photo.')
    mismatches = [field for field in ('view', 'lighting', 'makeup') if a[field] != b[field] or a[field] in (None, 'unknown')]
    if abs(a['width']/a['height'] - b['width']/b['height']) > .05:
        mismatches.append('aspect_ratio')
    usage = [r for r in store.list_progress(user.id, 'usage')
             if r['payload']['started_on'] <= a['captured_on'] and r['payload']['ended_on'] >= b['captured_on']]
    return {'before': before, 'after': after, 'usage_reports': usage, 'capture_differences': mismatches,
            'slider_allowed': not mismatches,
            'interpretation': 'Observed photos and self-reported use. Lighting, routine and other factors may contribute; this does not establish a product effect.'}


@router.get('/model-readiness')
def readiness(user: CurrentUser, store: StoreDep):
    consent = store.active_consent(user.id, 'model_training')
    return {'status': 'not_validated', 'outcome_prediction_available': False,
            'own_usage_reports': len(store.list_progress(user.id, 'usage')),
            'own_photos': len(store.list_progress(user.id, 'photo')),
            'training_consent_active': consent is not None,
            'reason': 'No validated product-outcome model is deployed. Collected records are observations, not proof of causation. Training is not running.'}


@router.post('/recommendation-feedback', dependencies=[require_consent('service')])
async def recommendation_feedback(body: RecommendationFeedback, user: CurrentUser, store: StoreDep):
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, 'service'):
            raise ApiError(403, 'consent_required', 'Account saving must be enabled.')
        event = next((r for r in store.list_progress(user.id, 'recommendation') if r['id'] == str(body.recommendation_id)), None)
        if event is None or body.product_id not in {item['product']['product_id'] for item in event['payload']['result']['items']}:
            raise not_found('Recommendation')
        values = body.model_dump(mode='json', exclude={'entry_id'})
        consent = store.active_consent(user.id, 'model_training')
        payload = {**values, 'training_consent_at_collection': str(consent.id) if consent else None}
        return store.create_progress(user.id, body.entry_id, 'feedback', payload, fingerprint(values))
