"""OpenAI service for AI-powered features.

This service provides:
- Chat completions
- Data analysis
- Text summarization
- MCP tool execution
- Usage tracking
"""
import json
import logging
import uuid
from typing import Optional, Dict, Any, List

from config import config

logger = logging.getLogger(__name__)

# Lazy-loaded usage repo
_ai_usage_repo = None


def _get_ai_usage_repo():
    """Get AI usage repository (lazy loaded)."""
    global _ai_usage_repo
    if _ai_usage_repo is None:
        try:
            from fin_server.repository.mongo_helper import get_collection
            _ai_usage_repo = get_collection('ai_usage')
        except Exception as e:
            logger.warning(f"Could not initialize AI usage repo: {e}")
    return _ai_usage_repo


class OpenAIService:
    """Service for interacting with OpenAI API."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAIService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._api_key = config.OPENAI_API_KEY
            self._default_model = config.OPENAI_MODEL
            self._client = None

            if self._api_key:
                self._init_client()

            self._initialized = True

    def _init_client(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
            logger.info("OpenAI client initialized successfully")
        except ImportError:
            logger.error("OpenAI package not installed. Run: pip install openai")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self._client = None

    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured."""
        return bool(self._api_key and self._client)

    def _log_usage(
        self,
        account_key: str,
        user_key: str,
        tokens: Dict[str, int],
        model: str = None,
        endpoint: str = None,
        tool_name: str = None,
        success: bool = True,
        error: str = None
    ) -> Optional[str]:
        """Log AI usage to the database."""
        repo = _get_ai_usage_repo()
        if not repo:
            return None

        try:
            request_id = str(uuid.uuid4())
            return repo.log_usage(
                account_key=account_key,
                user_key=user_key,
                request_id=request_id,
                tokens=tokens,
                model=model,
                endpoint=endpoint,
                tool_name=tool_name,
                success=success,
                error=error
            )
        except Exception as e:
            logger.warning(f"Failed to log AI usage: {e}")
            return None

    def list_models(self) -> List[str]:
        """List available OpenAI models."""
        if not self.is_configured():
            return []

        try:
            models = self._client.models.list()
            return [m.id for m in models.data if 'gpt' in m.id.lower()]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    # =========================================================================
    # Query Methods
    # =========================================================================

    def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single query to OpenAI.

        Args:
            prompt: The user's query
            model: Model to use (default from config)
            max_tokens: Maximum tokens in response
            temperature: Creativity (0-2, default 0.7)
            system_prompt: Optional system context

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self._chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Multi-turn chat conversation.

        Args:
            messages: List of message dicts with role and content
            model: Model to use
            max_tokens: Maximum tokens
            temperature: Creativity

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        return self._chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Internal method to call OpenAI chat completion API."""
        model = model or self._default_model

        kwargs = {
            "model": model,
            "messages": messages,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]

            return {
                "content": choice.message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                "finish_reason": choice.finish_reason,
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    # =========================================================================
    # Specialized Methods
    # =========================================================================

    def analyze_data(
        self,
        data: Any,
        question: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze data using AI.

        Args:
            data: Data to analyze (dict, list, or string)
            question: Question about the data
            context: Optional context about the data

        Returns:
            Analysis result
        """
        # Convert data to string if needed
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, indent=2, default=str)
        else:
            data_str = str(data)

        system_prompt = """You are a data analyst assistant. Analyze the provided data and answer questions about it.
Be specific, cite numbers from the data, and provide actionable insights."""

        if context:
            system_prompt += f"\n\nContext: {context}"

        prompt = f"""Data:
```json
{data_str}
```

Question: {question}

Please analyze the data and provide a detailed answer."""

        return self.query(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=config.OPENAI_MAX_TOKENS,
        )

    def summarize(
        self,
        text: str,
        max_length: str = "medium",
    ) -> Dict[str, Any]:
        """Summarize text.

        Args:
            text: Text to summarize
            max_length: "short" (1-2 sentences), "medium" (paragraph), "long" (detailed)

        Returns:
            Summary result
        """
        length_instructions = {
            "short": "Provide a 1-2 sentence summary.",
            "medium": "Provide a concise paragraph summary (3-5 sentences).",
            "long": "Provide a detailed summary with key points.",
        }

        instruction = length_instructions.get(max_length, length_instructions["medium"])

        system_prompt = f"You are a summarization assistant. {instruction}"

        prompt = f"Please summarize the following text:\n\n{text}"

        return self.query(
            prompt=prompt,
            system_prompt=system_prompt,
        )

    # =========================================================================
    # MCP Tool Methods
    # =========================================================================

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tools."""
        return [
            {
                "name": "query_database",
                "description": "Query the application database",
                "parameters": {
                    "collection": "string",
                    "query": "object",
                    "limit": "number (optional)",
                }
            },
            {
                "name": "analyze_fish_data",
                "description": "Analyze fish farming data",
                "parameters": {
                    "species_code": "string (optional)",
                    "pond_id": "string (optional)",
                    "date_range": "object (optional)",
                }
            },
            {
                "name": "generate_report",
                "description": "Generate an AI-powered report",
                "parameters": {
                    "report_type": "string",
                    "parameters": "object",
                }
            },
            {
                "name": "predict_growth",
                "description": "Predict fish growth based on historical data",
                "parameters": {
                    "species_code": "string",
                    "current_age_months": "number",
                    "current_weight": "number",
                }
            },
        ]

    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        tool_handlers = {
            "query_database": self._tool_query_database,
            "analyze_fish_data": self._tool_analyze_fish_data,
            "generate_report": self._tool_generate_report,
            "predict_growth": self._tool_predict_growth,
        }

        handler = tool_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown tool: {tool_name}")

        return handler(params=parameters)

    def _tool_query_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database query tool."""
        # This would integrate with your repositories
        collection = params.get("collection")
        query = params.get("query", {})
        limit = params.get("limit", 10)

        # Placeholder - integrate with actual repos
        return {
            "status": "success",
            "message": f"Would query {collection} with {query}, limit {limit}",
            "data": [],
        }

    def _tool_analyze_fish_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze fish data tool."""
        species_code = params.get("species_code")
        pond_id = params.get("pond_id")

        # Placeholder - integrate with fish analytics
        return {
            "status": "success",
            "message": f"Analyzing fish data for species={species_code}, pond={pond_id}",
            "analysis": {},
        }

    def _tool_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report tool."""
        report_type = params.get("report_type")
        report_params = params.get("parameters", {})

        # Use AI to generate report
        prompt = f"Generate a {report_type} report with parameters: {json.dumps(report_params)}"

        if self.is_configured():
            result = self.query(
                prompt=prompt,
                system_prompt="You are a report generation assistant for a fish farming application.",
            )
            return {
                "status": "success",
                "report_type": report_type,
                "content": result.get("content"),
            }

        return {
            "status": "error",
            "message": "OpenAI not configured",
        }

    def _tool_predict_growth(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Predict fish growth tool."""
        species_code = params.get("species_code")
        current_age = params.get("current_age_months")
        current_weight = params.get("current_weight")

        # Placeholder - would use AI + historical data
        return {
            "status": "success",
            "species_code": species_code,
            "current_age_months": current_age,
            "current_weight": current_weight,
            "predicted_weights": {
                "1_month": current_weight * 1.15 if current_weight else None,
                "3_months": current_weight * 1.5 if current_weight else None,
                "6_months": current_weight * 2.2 if current_weight else None,
            },
        }

