from flask import Blueprint, request, current_app
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.security.authentication import get_auth_payload
from fin_server.dto.growth_dto import GrowthRecordDTO

sampling_bp = Blueprint('sampling', __name__, url_prefix='/sampling')
repo = MongoRepositorySingleton.get_instance()

@sampling_bp.route('/', methods=['POST'])
def create_sampling_route():
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # Build DTO from request
        dto = GrowthRecordDTO.from_request(data)
        dto.recordedBy = payload.get('user_key')
        try:
            res = dto.save(repo=repo, collection_name='sampling')
            inserted_id = getattr(res, 'inserted_id', res)
            inserted_id = str(inserted_id) if inserted_id is not None else None
        except Exception:
            sr = repo.get_collection('sampling')
            rr = sr.insert_one(dto.to_db_doc())
            inserted_id = str(rr.inserted_id)
        dto.id = inserted_id
        return respond_success(dto.to_dict(), status=201)
    except Exception:
        current_app.logger.exception('Error in create_sampling_route')
        return respond_error('Server error', status=500)

@sampling_bp.route('/<pond_id>', methods=['GET'])
def list_sampling_for_pond_route(pond_id):
    try:
        sr = repo.get_collection('sampling')
        recs = list(sr.find({'pondId': pond_id}).sort('created_at', -1))
        out = []
        for r in recs:
            ro = normalize_doc(r)
            try:
                dto = GrowthRecordDTO.from_doc(ro)
                out.append(dto.to_dict())
            except Exception:
                ro['_id'] = str(ro.get('_id'))
                ro['id'] = ro['_id']
                out.append(ro)
        return respond_success(out)
    except Exception:
        current_app.logger.exception('Error in list_sampling_for_pond_route')
        return respond_error('Server error', status=500)

from flask import Blueprint as _Blueprint

sampling_api_bp = _Blueprint('sampling_api', __name__, url_prefix='/api')

@sampling_api_bp.route('/sampling', methods=['POST'])
def api_create_sampling():
    return create_sampling_route()

@sampling_api_bp.route('/sampling/<pond_id>', methods=['GET'])
def api_list_sampling_for_pond(pond_id):
    return list_sampling_for_pond_route(pond_id)
