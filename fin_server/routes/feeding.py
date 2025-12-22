from flask import Blueprint, request, current_app
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.security.authentication import get_auth_payload
from fin_server.dto.feeding_dto import FeedingRecordDTO

feeding_bp = Blueprint('feeding', __name__, url_prefix='/feeding')
repo = MongoRepositorySingleton.get_instance()

@feeding_bp.route('/', methods=['POST'])
def create_feeding_route():
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # Build DTO from request (accepts multiple variants)
        dto = FeedingRecordDTO.from_request(data)
        # Ensure recordedBy is set from token
        dto.recordedBy = payload.get('user_key')
        # Persist using DTO helper
        try:
            res = dto.save(repo=repo, collection_name='feeding')
            # repo.create may return inserted id or pymongo result
            try:
                inserted_id = getattr(res, 'inserted_id', res)
            except Exception:
                inserted_id = res
            inserted_id = str(inserted_id) if inserted_id is not None else None
        except Exception:
            # fallback to direct collection insert
            fr = repo.get_collection('feeding')
            r = fr.insert_one(dto.to_db_doc())
            inserted_id = str(r.inserted_id)
        dto.id = inserted_id
        return respond_success(dto.to_dict(), status=201)
    except Exception:
        current_app.logger.exception('Error in create_feeding_route')
        return respond_error('Server error', status=500)

@feeding_bp.route('/', methods=['GET'])
def list_feeding_route():
    try:
        payload = get_auth_payload(request)
        q = {}
        pondId = request.args.get('pondId') or request.args.get('pond_id')
        if pondId:
            q['pondId'] = pondId
        try:
            feeds = repo.feeding.find(q)
        except Exception:
            fr = repo.get_collection('feeding')
            feeds = list(fr.find(q).sort('created_at', -1))
        out = []
        for f in feeds:
            # normalize doc and convert via DTO
            fo = normalize_doc(f)
            try:
                feed_dto = FeedingRecordDTO.from_doc(fo)
                out.append(feed_dto.to_dict())
            except Exception:
                # fallback: include normalized doc with id
                fo['_id'] = str(fo.get('_id'))
                fo['id'] = fo.get('_id')
                out.append(fo)
        return respond_success(out)
    except Exception:
        current_app.logger.exception('Error in list_feeding_route')
        return respond_error('Server error', status=500)

@feeding_bp.route('/pond/<pond_id>', methods=['GET'])
def feeding_by_pond_route(pond_id):
    try:
        fr = repo.get_collection('feeding')
        feeds = list(fr.find({'pondId': pond_id}).sort('created_at', -1))
        out = []
        for f in feeds:
            fo = normalize_doc(f)
            try:
                feed_dto = FeedingRecordDTO.from_doc(fo)
                out.append(feed_dto.to_dict())
            except Exception:
                fo['_id'] = str(fo.get('_id'))
                fo['id'] = fo.get('_id')
                out.append(fo)
        return respond_success(out)
    except Exception:
        current_app.logger.exception('Error in feeding_by_pond_route')
        return respond_error('Server error', status=500)

from flask import Blueprint as _Blueprint

feeding_api_bp = _Blueprint('feeding_api', __name__, url_prefix='/api')

@feeding_api_bp.route('/feeding', methods=['POST'])
def api_create_feeding():
    return create_feeding_route()

@feeding_api_bp.route('/feeding', methods=['GET'])
def api_list_feeding():
    return list_feeding_route()

@feeding_api_bp.route('/feeding/pond/<pond_id>', methods=['GET'])
def api_feeding_by_pond(pond_id):
    return feeding_by_pond_route(pond_id)
