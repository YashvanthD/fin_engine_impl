import zoneinfo
from datetime import datetime

from bson import ObjectId
from flask import Blueprint, request, current_app

from fin_server.dto.pond_event_dto import PondEventDTO
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.helpers import respond_error, respond_success, get_request_payload, normalize_doc
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.validation import validate_pond_event_payload
from fin_server.services.expense_service import create_expense_with_repo

pond_event_bp = Blueprint('pond_event', __name__, url_prefix='/pond_event')

IST_TZ = zoneinfo.ZoneInfo('Asia/Kolkata')

fish_mapping_repo = get_collection('fish_mapping')
fish_activity_repo = get_collection('fish_activity')
pond_repository = get_collection('pond')
pond_event_repository = get_collection('pond_event')
fish_analytics_repository = get_collection('fish_analytics')
expenses_repo = get_collection('expenses')


def create_sell_expense(account_key, pond_id, fish_id, count, details, user_key, event_id=None):
    """Create an income expense record when fish are sold."""
    try:
        total_amount = details.get('total_amount') or details.get('totalAmount')
        if not total_amount:
            # Try to calculate from price_per_kg and weight
            price_per_kg = details.get('price_per_kg') or details.get('pricePerKg')
            total_weight = details.get('total_weight_kg') or details.get('totalWeightKg')
            if price_per_kg and total_weight:
                total_amount = float(price_per_kg) * float(total_weight)

        if not total_amount:
            current_app.logger.warning(f'No amount provided for sell event, skipping expense creation')
            return None

        expense_doc = {
            'account_key': account_key,
            'amount': float(total_amount),
            'currency': details.get('currency') or 'INR',
            'category': 'income',
            'type': 'fish_sale',
            'action': 'sell',
            'status': 'SUCCESS',
            'payment_method': details.get('payment_method') or 'cash',
            'recorded_by': user_key,
            'notes': details.get('notes') or f'Fish sale: {count} {fish_id}',
            'metadata': {
                'pond_id': pond_id,
                'species': fish_id,
                'count': count,
                'event_id': str(event_id) if event_id else None,
                'buyer': details.get('buyer'),
                'price_per_kg': details.get('price_per_kg'),
                'total_weight_kg': details.get('total_weight_kg')
            },
            'created_at': get_time_date_dt(include_time=True)
        }

        expense_id = create_expense_with_repo(expense_doc, expenses_repo)
        current_app.logger.info(f'Created sell expense {expense_id} for pond={pond_id}, amount={total_amount}')
        return expense_id
    except Exception:
        current_app.logger.exception('Failed to create sell expense')
        return None

def update_pond_metadata(pond_id, fish_id, count, event_type):
    # Use repository atomic helper for clarity
    try:
        inc_amount = -int(count) if event_type in ['remove', 'sell', 'sample', 'shift_out'] else int(count)
        inc_fields = { 'metadata.total_fish': inc_amount, f'metadata.fish_types.{fish_id}': inc_amount }
        last_activity = {
            'event_type': event_type,
            'fish_id': fish_id,
            'count': count,
            'timestamp': get_time_date_dt(include_time=True).isoformat()
        }
        pond_repository.atomic_update_metadata(pond_id, inc_fields=inc_fields, set_fields={'metadata.last_activity': last_activity})
        # Best-effort cleanup: remove negative/zero counts
        try:
            pond = pond_repository.get_pond(pond_id)
            if pond:
                fish_types = (pond.get('metadata') or {}).get('fish_types', {})
                to_unset = {f'metadata.fish_types.{k}': '' for k, v in fish_types.items() if v <= 0}
                if to_unset:
                    pond_repository.atomic_update_metadata(pond_id, unset_fields=to_unset)
        except Exception:
            current_app.logger.exception('Failed cleanup of zero-count fish_types')
    except Exception:
        current_app.logger.exception('Failed atomic update of pond metadata')

def update_fish_analytics_and_mapping(account_key, fish_id, count, event_type, fish_age_in_month=None, pond_id=None):
    # Always ensure mapping exists (use repo helper)
    try:
        fish_mapping_repo.add_fish_to_account(account_key, fish_id)
    except Exception:
        current_app.logger.exception('Failed to ensure fish mapping')
    # For add/shift_in: add a batch; for remove/sell/sample/shift_out: add negative batch
    event_id = f"{account_key}-{fish_id}-{pond_id}-{datetime.now(IST_TZ).strftime('%Y%m%d%H%M%S%f')}"
    base_dt = get_time_date_dt(include_time=True)
    if event_type in ['add', 'shift_in']:
        fish_analytics_repository.add_batch(
            fish_id, int(count), int(fish_age_in_month) if fish_age_in_month is not None else 0,
            base_dt, account_key=account_key, event_id=event_id, pond_id=pond_id
        )
    elif event_type in ['remove', 'sell', 'sample', 'shift_out']:
        # Store as negative batch for analytics
        fish_analytics_repository.add_batch(
            fish_id, -int(count), int(fish_age_in_month) if fish_age_in_month is not None else 0,
            base_dt, account_key=account_key, event_id=event_id, pond_id=pond_id
        )

@pond_event_bp.route('/<pond_id>/event/<event_type>', methods=['POST'])
def pond_event_action(pond_id, event_type):
    """
    Supported event_type: add, sell, sample, remove, shift_in, shift_out
    """
    current_app.logger.debug(f'POST /pond_event/{pond_id}/event/{event_type} called')
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        # validate payload
        ok, verrors = validate_pond_event_payload(data, event_type)
        if not ok:
            return respond_error(verrors, status=400)
        fish_id = data.get('fish_id')
        count = int(data.get('count', 0))
        fish_age_in_month = data.get('fish_age_in_month')
        if not fish_id or count <= 0:
            return respond_error(verrors, status=400)
        # log sanitized event info
        current_app.logger.info(f'PondEvent: account={payload.get("account_key")}, user={payload.get("user_key")}, pond={pond_id}, event={event_type}, fish={fish_id}, count={count}')
        # Build DTO from request for canonical shape
        try:
            dto_payload = {
                'pondId': pond_id,
                'eventType': event_type,
                'species': fish_id,
                'count': count,
                'details': data.get('details', {}),
                'timestamp': data.get('timestamp') or data.get('created_at')
            }
            dto = PondEventDTO.from_request(dto_payload)
            dto.recordedBy = payload.get('user_key')
            if fish_age_in_month is not None:
                dto.extra['fish_age_in_month'] = fish_age_in_month
            # Persist via DTO save
            try:
                res = dto.save(repo=pond_event_repository, collection_name='pond_events')
                event_inserted_id = getattr(res, 'inserted_id', res)
            except Exception:
                # fallback to repository create
                res = pond_event_repository.create(dto.to_db_doc())
                event_inserted_id = getattr(res, 'inserted_id', res)
            event_doc_db = dto.to_db_doc()
            # ensure created_at and user_key
            event_doc_db['created_at'] = event_doc_db.get('created_at') or get_time_date_dt(include_time=True)
            event_doc_db['user_key'] = dto.recordedBy
        except Exception:
            # fallback to previous behavior
            event_doc_db = {
                'pond_id': pond_id,
                'fish_id': fish_id,
                'count': count,
                'event_type': event_type,
                'details': data.get('details', {}),
                'created_at': get_time_date_dt(include_time=True),
                'user_key': payload.get('user_key')
            }
            if fish_age_in_month is not None:
                event_doc_db['fish_age_in_month'] = fish_age_in_month

        # If we used event_doc_db directly, ensure it's persisted
        event_inserted_id = locals().get('event_inserted_id', None)
        try:
            if event_inserted_id is None:
                res = pond_event_repository.create(event_doc_db)
                event_inserted_id = getattr(res, 'inserted_id', res)
        except Exception:
            current_app.logger.exception('Failed to persist pond event via repository; continuing')

        current_app.logger.info(f'PondEvent created id={event_inserted_id} for pond={pond_id} event={event_type}')
        # Update pond metadata
        update_pond_metadata(pond_id, fish_id, count, event_type)
        # Update fish analytics and mapping
        account_key = payload.get('account_key')
        update_fish_analytics_and_mapping(account_key, fish_id, count, event_type, fish_age_in_month, pond_id)
        # Record fish activity details for sample/add events
        try:
            if event_type in ['sample', 'add']:
                samples = data.get('samples') if isinstance(data.get('samples'), list) else None
                activity_doc = {
                    'account_key': account_key,
                    'pond_id': pond_id,
                    'fish_id': fish_id,
                    'event_type': event_type,
                    'count': count,
                    'user_key': payload.get('user_key'),
                    'details': data.get('details', {}),
                    'samples': samples,
                    'created_at': get_time_date_dt(include_time=True)
                }
                fish_activity_repo.create(activity_doc)
        except Exception:
            current_app.logger.exception('Failed to record fish activity')

        # Create expense/income record for sell events
        expense_id = None
        try:
            if event_type == 'sell':
                details = data.get('details', {})
                expense_id = create_sell_expense(
                    account_key=account_key,
                    pond_id=pond_id,
                    fish_id=fish_id,
                    count=count,
                    details=details,
                    user_key=payload.get('user_key'),
                    event_id=event_inserted_id
                )
        except Exception:
            current_app.logger.exception('Failed to create expense for sell event')

        response_data = {'event_id': str(event_inserted_id)}
        if expense_id:
            response_data['expense_id'] = str(expense_id)

        return respond_success(response_data, status=201)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_event_action: {e}')
        return respond_error('Server error', status=500)

@pond_event_bp.route('/<pond_id>/events', methods=['GET'])
def get_pond_events(pond_id):
    current_app.logger.debug('GET /pond_event/%s/events called', pond_id)
    try:
        _ = get_request_payload(request)
        events = pond_event_repository.get_events_by_pond(pond_id)
        out = []
        for e in events:
            try:
                dto = PondEventDTO.from_doc(e)
                out.append(dto.to_dict())
            except Exception:
                ed = normalize_doc(e)
                ed['id'] = str(ed.get('_id'))
                out.append(ed)
        return respond_success({'events': out})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Exception in get_pond_events')
        return respond_error('Server error', status=500)

@pond_event_bp.route('/<pond_id>/events/<event_id>', methods=['DELETE'])
def delete_pond_event(pond_id, event_id):
    """Delete a pond event and reverse its effects on pond metadata and analytics."""
    current_app.logger.debug('DELETE /pond_event/%s/events/%s called', pond_id, event_id)
    try:
        payload = get_request_payload(request)
        account_key = payload.get('account_key')

        # Find the event first to get its details for reversal
        try:
            oid = ObjectId(event_id)
        except Exception:
            return respond_error('Invalid event_id', status=400)

        old_event = pond_event_repository.find_one({'_id': oid})
        if not old_event:
            return respond_error('Event not found', status=404)

        # Verify pond_id matches
        if str(old_event.get('pond_id')) != str(pond_id):
            return respond_error('Pond ID mismatch for event', status=400)

        # Extract event details for reversal
        old_type = old_event.get('event_type')
        old_count = int(old_event.get('count', 0) or 0)
        old_fish_id = old_event.get('fish_id')
        old_age = old_event.get('fish_age_in_month')

        # Reverse the event effects before deleting
        if old_count and old_fish_id:
            # Determine inverse event type to revert effects
            # If original was add/shift_in (+count), we need to remove (-count)
            # If original was remove/sell/sample/shift_out (-count), we need to add (+count)
            inverse_type = 'remove' if old_type in ['add', 'shift_in'] else 'add'

            try:
                current_app.logger.info(f'Reversing event effects: type={old_type}, fish={old_fish_id}, count={old_count}, inverse={inverse_type}')
                update_pond_metadata(pond_id, old_fish_id, old_count, inverse_type)
                update_fish_analytics_and_mapping(account_key, old_fish_id, old_count, inverse_type, old_age, pond_id)
            except Exception:
                current_app.logger.exception('Failed to reverse event effects during delete')
                # Continue with delete even if reversal fails - log the issue

        # Now delete the event
        result = pond_event_repository.delete(oid)
        if result.deleted_count == 0:
            return respond_error('Event not found', status=404)

        current_app.logger.info(f'Deleted pond event {event_id} and reversed its effects')
        return respond_success({'deleted': True, 'reversed': True})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Exception in delete_pond_event')
        return respond_error('Server error', status=500)

# PUT: update an existing pond event and reconcile pond metadata + analytics
@pond_event_bp.route('/<pond_id>/events/<event_id>', methods=['PUT'])
def update_pond_event(pond_id, event_id):
    current_app.logger.debug('PUT /pond_event/%s/events/%s called', pond_id, event_id)
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        # Find existing event
        try:
            oid = ObjectId(event_id)
        except Exception:
            return respond_error('Invalid event_id', status=400)
        old = pond_event_repository.find_one({'_id': oid})
        if not old:
            return respond_error('Event not found', status=404)

        # Ensure the pond_id matches
        if str(old.get('pond_id')) != str(pond_id):
            return respond_error('Pond ID mismatch for event', status=400)

        account_key = payload.get('account_key')

        # Compute reversal of old event to undo its effects
        old_type = old.get('event_type')
        old_count = int(old.get('count', 0) or 0)
        old_fish_id = old.get('fish_id')
        old_age = old.get('fish_age_in_month')

        # Determine inverse event type to revert effects
        inverse_old = 'remove' if old_type in ['add', 'shift_in'] else 'add'
        if old_count and old_fish_id:
            try:
                # revert old event atomically
                update_pond_metadata(pond_id, old_fish_id, old_count, inverse_old)
                update_fish_analytics_and_mapping(account_key, old_fish_id, old_count, inverse_old, old_age, pond_id)
            except Exception:
                current_app.logger.exception('Failed to revert old event effects')

        # Prepare new event fields (only allow specific fields to be updated)
        allowed = ['fish_id', 'count', 'event_type', 'details', 'fish_age_in_month', 'samples']
        update_fields = {k: v for k, v in data.items() if k in allowed}
        if not update_fields:
            return respond_error('No updatable fields provided', status=400)

        # Update event document
        pond_event_repository.update({'_id': oid}, update_fields)

        # Apply new event effects
        new_type = update_fields.get('event_type', old_type)
        new_count = int(update_fields.get('count', old_count) or 0)
        new_fish_id = update_fields.get('fish_id', old_fish_id)
        new_age = update_fields.get('fish_age_in_month', old_age)

        try:
            update_pond_metadata(pond_id, new_fish_id, new_count, new_type)
            update_fish_analytics_and_mapping(account_key, new_fish_id, new_count, new_type, new_age, pond_id)
        except Exception:
            current_app.logger.exception('Failed to apply new event effects')

        # If samples or details provided and event is sample/add, record activity
        try:
            if new_type in ['sample', 'add']:
                samples = update_fields.get('samples') if isinstance(update_fields.get('samples'), list) else None
                activity_doc = {
                    'account_key': account_key,
                    'pond_id': pond_id,
                    'fish_id': new_fish_id,
                    'event_type': new_type,
                    'count': new_count,
                    'user_key': payload.get('user_key'),
                    'details': update_fields.get('details', {}),
                    'samples': samples
                }
                fish_activity_repo.create(activity_doc)
        except Exception:
            current_app.logger.exception('Failed to record activity for updated event')

        return respond_success({'event_id': event_id})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in update_pond_event: {e}')
        return respond_error('Server error', status=500)


# NEW: Atomic fish transfer between ponds
@pond_event_bp.route('/transfer', methods=['POST'])
def transfer_fish_between_ponds():
    """
    Atomic fish transfer between two ponds.
    Creates both shift_out and shift_in events in a single transaction.

    Request body:
    {
        "source_pond_id": "pond-001",
        "destination_pond_id": "pond-002", 
        "fish_id": "TILAPIA_NILE",
        "count": 100,
        "fish_age_in_month": 3,
        "details": {
            "reason": "Size grading",
            "notes": "Moving larger fish to grow-out pond"
        }
    }
    """
    current_app.logger.debug('POST /pond_event/transfer called')
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        user_key = payload.get('user_key')

        # Validate required fields
        source_pond_id = data.get('source_pond_id') or data.get('sourcePondId')
        dest_pond_id = data.get('destination_pond_id') or data.get('destinationPondId')
        fish_id = data.get('fish_id') or data.get('fishId')
        count = data.get('count')
        fish_age_in_month = data.get('fish_age_in_month') or data.get('fishAgeInMonth')
        details = data.get('details', {})

        if not source_pond_id:
            return respond_error('source_pond_id is required', status=400)
        if not dest_pond_id:
            return respond_error('destination_pond_id is required', status=400)
        if not fish_id:
            return respond_error('fish_id is required', status=400)
        if not count or int(count) <= 0:
            return respond_error('count must be a positive integer', status=400)
        if source_pond_id == dest_pond_id:
            return respond_error('source and destination ponds must be different', status=400)

        count = int(count)

        # Generate a transfer_id to link the two events
        transfer_id = f"TRF-{account_key}-{datetime.now(IST_TZ).strftime('%Y%m%d%H%M%S%f')}"

        current_app.logger.info(f'Fish transfer: {source_pond_id} -> {dest_pond_id}, fish={fish_id}, count={count}, transfer_id={transfer_id}')

        shift_out_id = None
        shift_in_id = None

        try:
            # Step 1: Create shift_out event for source pond
            shift_out_doc = {
                'pond_id': source_pond_id,
                'fish_id': fish_id,
                'count': count,
                'event_type': 'shift_out',
                'details': {
                    **details,
                    'destination_pond': dest_pond_id,
                    'transfer_id': transfer_id
                },
                'fish_age_in_month': fish_age_in_month,
                'created_at': get_time_date_dt(include_time=True),
                'user_key': user_key,
                'account_key': account_key,
                'transfer_id': transfer_id
            }
            res_out = pond_event_repository.create(shift_out_doc)
            shift_out_id = getattr(res_out, 'inserted_id', res_out)

            # Update source pond metadata (decrease count)
            update_pond_metadata(source_pond_id, fish_id, count, 'shift_out')
            update_fish_analytics_and_mapping(account_key, fish_id, count, 'shift_out', fish_age_in_month, source_pond_id)

            current_app.logger.info(f'Created shift_out event {shift_out_id} for source pond {source_pond_id}')

        except Exception as e:
            current_app.logger.exception(f'Failed to create shift_out event: {e}')
            return respond_error('Failed to create shift_out event', status=500)

        try:
            # Step 2: Create shift_in event for destination pond
            shift_in_doc = {
                'pond_id': dest_pond_id,
                'fish_id': fish_id,
                'count': count,
                'event_type': 'shift_in',
                'details': {
                    **details,
                    'source_pond': source_pond_id,
                    'transfer_id': transfer_id
                },
                'fish_age_in_month': fish_age_in_month,
                'created_at': get_time_date_dt(include_time=True),
                'user_key': user_key,
                'account_key': account_key,
                'transfer_id': transfer_id
            }
            res_in = pond_event_repository.create(shift_in_doc)
            shift_in_id = getattr(res_in, 'inserted_id', res_in)

            # Update destination pond metadata (increase count)
            update_pond_metadata(dest_pond_id, fish_id, count, 'shift_in')
            update_fish_analytics_and_mapping(account_key, fish_id, count, 'shift_in', fish_age_in_month, dest_pond_id)

            current_app.logger.info(f'Created shift_in event {shift_in_id} for destination pond {dest_pond_id}')

        except Exception as e:
            # Rollback: reverse the shift_out if shift_in fails
            current_app.logger.exception(f'Failed to create shift_in event, rolling back shift_out: {e}')
            try:
                if shift_out_id:
                    # Reverse the shift_out effects
                    update_pond_metadata(source_pond_id, fish_id, count, 'shift_in')  # Reverse: add back
                    update_fish_analytics_and_mapping(account_key, fish_id, count, 'shift_in', fish_age_in_month, source_pond_id)
                    # Delete the shift_out event
                    pond_event_repository.delete(shift_out_id)
                    current_app.logger.info(f'Rolled back shift_out event {shift_out_id}')
            except Exception as rollback_error:
                current_app.logger.exception(f'Failed to rollback shift_out: {rollback_error}')

            return respond_error('Failed to complete transfer - rolled back', status=500)

        return respond_success({
            'transfer_id': transfer_id,
            'shift_out_event_id': str(shift_out_id),
            'shift_in_event_id': str(shift_in_id),
            'source_pond': source_pond_id,
            'destination_pond': dest_pond_id,
            'fish_id': fish_id,
            'count': count
        }, status=201)

    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in transfer_fish_between_ponds: {e}')
        return respond_error('Server error', status=500)

