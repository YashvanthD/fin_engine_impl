from flask import Blueprint, current_app
from fin_server.utils.helpers import respond_error

compat_bp = Blueprint('compat_deprecated', __name__, url_prefix='/api/compat')

@compat_bp.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@compat_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def deprecated(path):
    current_app.logger.warning(f"Deprecated compat endpoint called: /api/compat/{path} - advise using canonical /api routes")
    return respond_error('Compatibility endpoint deprecated. Use canonical /api endpoints.', status=410)
