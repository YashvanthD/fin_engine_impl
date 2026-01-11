"""OpenAI routes for AI-powered queries and actions.

This module provides endpoints for:
- Basic query/chat completions
- MCP (Model Context Protocol) integration
- AI-powered analytics and insights
"""
import logging
from flask import Blueprint, request

from config import config
from fin_server.services.ai.openai_service import OpenAIService
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error

logger = logging.getLogger(__name__)

# Blueprint
openai_bp = Blueprint('openai', __name__, url_prefix='/ai/openai')

# Service instance (lazy loaded)
_openai_service = None


def _get_openai_service() -> OpenAIService:
    """Get or create OpenAI service instance."""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@openai_bp.route('/health', methods=['GET'])
@handle_errors
def health_check():
    """Check if OpenAI service is configured and available."""
    service = _get_openai_service()
    is_configured = service.is_configured()

    return respond_success({
        'status': 'ok' if is_configured else 'not_configured',
        'configured': is_configured,
        'model': config.OPENAI_MODEL if is_configured else None,
    })


@openai_bp.route('/models', methods=['GET'])
@handle_errors
@require_auth
def list_models(auth_payload):
    """List available OpenAI models."""
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    models = service.list_models()
    return respond_success({'models': models})


# =============================================================================
# Usage Statistics Endpoints
# =============================================================================

@openai_bp.route('/usage', methods=['GET'])
@handle_errors
@require_auth
def get_usage(auth_payload):
    """Get AI usage statistics for the current account.

    Query params:
        days: Number of days to look back (default: 30)
    """
    from fin_server.repository.mongo_helper import get_collection

    ai_usage_repo = get_collection('ai_usage')
    if not ai_usage_repo:
        return respond_error('Usage tracking not available', status=503)

    account_key = auth_payload.get('account_key')

    # Get summary
    summary = ai_usage_repo.get_usage_summary(account_key)

    # Get usage by model
    by_model = ai_usage_repo.get_usage_by_model(account_key)

    # Get daily usage
    days = int(request.args.get('days', 30))
    daily = ai_usage_repo.get_daily_usage(account_key, days=days)

    # Get image usage stats
    image_usage = ai_usage_repo.get_image_usage_summary(account_key)

    return respond_success({
        'summary': summary,
        'by_model': by_model,
        'daily_usage': daily,
        'image_usage': image_usage,
    })


@openai_bp.route('/usage/history', methods=['GET'])
@handle_errors
@require_auth
def get_usage_history(auth_payload):
    """Get detailed AI usage history.

    Query params:
        limit: Max records (default: 50)
        skip: Records to skip (default: 0)
    """
    from fin_server.repository.mongo_helper import get_collection

    ai_usage_repo = get_collection('ai_usage')
    if not ai_usage_repo:
        return respond_error('Usage tracking not available', status=503)

    account_key = auth_payload.get('account_key')
    limit = int(request.args.get('limit', 50))
    skip = int(request.args.get('skip', 0))

    records = ai_usage_repo.get_by_account(account_key, limit=limit)

    # Clean up records for response
    results = []
    for r in records:
        r['_id'] = str(r.get('_id', ''))
        r['created_at'] = str(r.get('created_at', ''))
        results.append(r)

    return respond_success({
        'records': results,
        'count': len(results),
    })



# =============================================================================
# Query Endpoints
# =============================================================================

@openai_bp.route('/query', methods=['POST'])
@handle_errors
@require_auth
def query(auth_payload):
    """Send a query to OpenAI and get a response. Optionally include an image.

    Request body (JSON):
    {
        "prompt": "Your question here",
        "model": "gpt-4o-mini",  // optional
        "max_tokens": 1000,      // optional
        "temperature": 0.7,      // optional
        "system_prompt": "...",  // optional
        "image_url": "https://...",  // optional - for vision
        "image_base64": "...",   // optional - for vision
        "detail": "auto"         // optional - "low", "high", "auto"
    }

    OR multipart/form-data (for file upload):
    - prompt: text field (required)
    - image: file (optional)
    - model: text field (optional)
    - system_prompt: text field (optional)
    """
    import base64

    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    prompt = None
    model = None
    max_tokens = None
    temperature = None
    system_prompt = None
    image_url = None
    image_base64 = None
    detail = "auto"

    # Handle multipart form data (file upload)
    if request.content_type and 'multipart/form-data' in request.content_type:
        prompt = request.form.get('prompt') or request.form.get('message') or request.form.get('query')
        model = request.form.get('model')
        max_tokens = int(request.form.get('max_tokens')) if request.form.get('max_tokens') else None
        temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
        system_prompt = request.form.get('system_prompt') or request.form.get('system')
        detail = request.form.get('detail', 'auto')

        # Handle optional image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
    else:
        # Handle JSON request
        data = request.get_json(force=True)

        prompt = data.get('prompt') or data.get('message') or data.get('query')
        model = data.get('model')
        max_tokens = data.get('max_tokens')
        temperature = data.get('temperature')
        system_prompt = data.get('system_prompt') or data.get('system')
        image_url = data.get('image_url') or data.get('url')
        image_base64 = data.get('image_base64') or data.get('base64') or data.get('image')
        detail = data.get('detail', 'auto')

    if not prompt:
        return respond_error('prompt is required', status=400)

    # If image is provided, use vision API
    if image_url or image_base64:
        response = service.analyze_image(
            image_url=image_url,
            image_base64=image_base64,
            prompt=f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
            model=model,
            max_tokens=max_tokens,
            account_key=auth_payload.get('account_key'),
            user_key=auth_payload.get('user_key'),
            detail=detail,
        )
    else:
        # Standard text query
        response = service.query(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            account_key=auth_payload.get('account_key'),
            user_key=auth_payload.get('user_key'),
            endpoint='/ai/openai/query',
        )

    return respond_success({
        'response': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
        'finish_reason': response.get('finish_reason'),
    })


@openai_bp.route('/chat', methods=['POST'])
@handle_errors
@require_auth
def chat(auth_payload):
    """Multi-turn chat conversation with OpenAI.

    Request body:
    {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ],
        "model": "gpt-4o-mini",  // optional
        "max_tokens": 1000,      // optional
        "temperature": 0.7       // optional
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    messages = data.get('messages')
    if not messages or not isinstance(messages, list):
        return respond_error('messages array is required', status=400)

    # Validate message format
    for msg in messages:
        if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
            return respond_error('Each message must have role and content', status=400)

    # Optional parameters
    model = data.get('model')
    max_tokens = data.get('max_tokens')
    temperature = data.get('temperature')

    response = service.chat(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        account_key=auth_payload.get('account_key'),
        user_key=auth_payload.get('user_key'),
        endpoint='/ai/openai/chat',
    )

    return respond_success({
        'message': response.get('content'),
        'role': 'assistant',
        'model': response.get('model'),
        'usage': response.get('usage'),
        'finish_reason': response.get('finish_reason'),
    })


# =============================================================================
# Specialized Query Endpoints
# =============================================================================

@openai_bp.route('/analyze', methods=['POST'])
@handle_errors
@require_auth
def analyze_data(auth_payload):
    """Analyze data using AI.

    Request body:
    {
        "data": {...} or [...],
        "question": "What trends do you see?",
        "context": "This is fish farm data..."  // optional
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    analysis_data = data.get('data')
    question = data.get('question') or data.get('prompt')
    context = data.get('context')

    if not analysis_data:
        return respond_error('data is required', status=400)
    if not question:
        return respond_error('question is required', status=400)

    response = service.analyze_data(
        data=analysis_data,
        question=question,
        context=context,
    )

    return respond_success({
        'analysis': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
    })


@openai_bp.route('/summarize', methods=['POST'])
@handle_errors
@require_auth
def summarize(auth_payload):
    """Summarize text or data.

    Request body:
    {
        "text": "Long text to summarize...",
        "max_length": "short" | "medium" | "long"  // optional
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    text = data.get('text') or data.get('content')
    if not text:
        return respond_error('text is required', status=400)

    max_length = data.get('max_length', 'medium')

    response = service.summarize(text=text, max_length=max_length)

    return respond_success({
        'summary': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
    })


# =============================================================================
# Image Analysis Endpoints (Vision API)
# =============================================================================

@openai_bp.route('/analyze-image', methods=['POST'])
@handle_errors
@require_auth
def analyze_image(auth_payload):
    """Analyze an image using OpenAI Vision.

    Request body (JSON):
    {
        "image_url": "https://example.com/image.jpg",  // OR
        "image_base64": "base64_encoded_image_data",
        "prompt": "What's in this image?",  // optional
        "model": "gpt-4o-mini",  // optional
        "max_tokens": 1000,  // optional
        "detail": "auto"  // optional: "low", "high", "auto"
    }

    OR multipart/form-data:
    - image: file upload
    - prompt: text field
    - model: text field (optional)
    """
    import base64

    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    image_url = None
    image_base64 = None
    prompt = "What's in this image? Describe it in detail."
    model = None
    max_tokens = None
    detail = "auto"

    # Handle multipart form data (file upload)
    if request.content_type and 'multipart/form-data' in request.content_type:
        if 'image' not in request.files:
            return respond_error('image file is required', status=400)

        image_file = request.files['image']
        if image_file.filename == '':
            return respond_error('No image selected', status=400)

        # Read and encode the image
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Get other form fields
        prompt = request.form.get('prompt', prompt)
        model = request.form.get('model')
        max_tokens = int(request.form.get('max_tokens')) if request.form.get('max_tokens') else None
        detail = request.form.get('detail', 'auto')
    else:
        # Handle JSON request
        data = request.get_json(force=True)

        image_url = data.get('image_url') or data.get('url')
        image_base64 = data.get('image_base64') or data.get('base64') or data.get('image')
        prompt = data.get('prompt') or data.get('question') or prompt
        model = data.get('model')
        max_tokens = data.get('max_tokens')
        detail = data.get('detail', 'auto')

    if not image_url and not image_base64:
        return respond_error('Either image_url or image_base64/image file is required', status=400)

    response = service.analyze_image(
        image_url=image_url,
        image_base64=image_base64,
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        account_key=auth_payload.get('account_key'),
        user_key=auth_payload.get('user_key'),
        detail=detail,
    )

    return respond_success({
        'analysis': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
        'finish_reason': response.get('finish_reason'),
    })


@openai_bp.route('/analyze-images', methods=['POST'])
@handle_errors
@require_auth
def analyze_multiple_images(auth_payload):
    """Analyze multiple images together.

    Request body:
    {
        "images": [
            {"url": "https://example.com/image1.jpg"},
            {"url": "https://example.com/image2.jpg"},
            {"base64": "base64_data", "mime_type": "image/png"}
        ],
        "prompt": "Compare these images",
        "model": "gpt-4o-mini",  // optional
        "max_tokens": 2000,  // optional
        "detail": "auto"  // optional
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    images = data.get('images')
    if not images or not isinstance(images, list):
        return respond_error('images array is required', status=400)

    if len(images) > 10:
        return respond_error('Maximum 10 images allowed', status=400)

    prompt = data.get('prompt') or "Analyze these images"
    model = data.get('model')
    max_tokens = data.get('max_tokens')
    detail = data.get('detail', 'auto')

    response = service.analyze_multiple_images(
        images=images,
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        account_key=auth_payload.get('account_key'),
        user_key=auth_payload.get('user_key'),
        detail=detail,
    )

    return respond_success({
        'analysis': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
        'finish_reason': response.get('finish_reason'),
    })


@openai_bp.route('/analyze-fish', methods=['POST'])
@handle_errors
@require_auth
def analyze_fish_image(auth_payload):
    """Specialized fish image analysis.

    Request body (JSON):
    {
        "image_url": "https://example.com/fish.jpg",  // OR
        "image_base64": "base64_encoded_image_data",
        "analysis_type": "general"  // "general", "health", "species", "size"
    }

    OR multipart/form-data:
    - image: file upload
    - analysis_type: text field
    """
    import base64

    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    image_url = None
    image_base64 = None
    analysis_type = "general"

    # Handle multipart form data (file upload)
    if request.content_type and 'multipart/form-data' in request.content_type:
        if 'image' not in request.files:
            return respond_error('image file is required', status=400)

        image_file = request.files['image']
        if image_file.filename == '':
            return respond_error('No image selected', status=400)

        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        analysis_type = request.form.get('analysis_type', 'general')
    else:
        data = request.get_json(force=True)
        image_url = data.get('image_url') or data.get('url')
        image_base64 = data.get('image_base64') or data.get('base64') or data.get('image')
        analysis_type = data.get('analysis_type', 'general')

    if not image_url and not image_base64:
        return respond_error('Either image_url or image_base64/image file is required', status=400)

    valid_types = ['general', 'health', 'species', 'size']
    if analysis_type not in valid_types:
        return respond_error(f'Invalid analysis_type. Must be one of: {valid_types}', status=400)

    response = service.analyze_fish_image(
        image_url=image_url,
        image_base64=image_base64,
        analysis_type=analysis_type,
        account_key=auth_payload.get('account_key'),
        user_key=auth_payload.get('user_key'),
    )

    return respond_success({
        'analysis_type': response.get('analysis_type'),
        'analysis': response.get('content'),
        'model': response.get('model'),
        'usage': response.get('usage'),
    })


# =============================================================================
# MCP (Model Context Protocol) Endpoints
# =============================================================================

@openai_bp.route('/mcp/tools', methods=['GET'])
@handle_errors
@require_auth
def list_mcp_tools(auth_payload):
    """List available MCP tools."""
    service = _get_openai_service()

    tools = service.get_available_tools()
    return respond_success({'tools': tools})


@openai_bp.route('/mcp/execute', methods=['POST'])
@handle_errors
@require_auth
def execute_mcp_tool(auth_payload):
    """Execute an MCP tool.

    Request body:
    {
        "tool": "tool_name",
        "parameters": {...}
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    tool_name = data.get('tool') or data.get('tool_name')
    parameters = data.get('parameters') or data.get('params') or {}

    if not tool_name:
        return respond_error('tool name is required', status=400)

    result = service.execute_tool(tool_name=tool_name, parameters=parameters)

    return respond_success({
        'tool': tool_name,
        'result': result,
    })

