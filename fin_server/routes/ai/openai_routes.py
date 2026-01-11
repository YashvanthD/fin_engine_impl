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
# Query Endpoints
# =============================================================================

@openai_bp.route('/query', methods=['POST'])
@handle_errors
@require_auth
def query(auth_payload):
    """Send a query to OpenAI and get a response.

    Request body:
    {
        "prompt": "Your question here",
        "model": "gpt-4o-mini",  // optional, uses default from config
        "max_tokens": 1000,      // optional
        "temperature": 0.7,      // optional
        "system_prompt": "..."   // optional system context
    }
    """
    service = _get_openai_service()

    if not service.is_configured():
        return respond_error('OpenAI is not configured', status=503)

    data = request.get_json(force=True)

    # Validate required fields
    prompt = data.get('prompt') or data.get('message') or data.get('query')
    if not prompt:
        return respond_error('prompt is required', status=400)

    # Optional parameters
    model = data.get('model')
    max_tokens = data.get('max_tokens')
    temperature = data.get('temperature')
    system_prompt = data.get('system_prompt') or data.get('system')

    # Call OpenAI
    response = service.query(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
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

