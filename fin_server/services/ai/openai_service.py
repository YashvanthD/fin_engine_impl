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
        error: str = None,
        image_attached: bool = False,
        image_url: str = None,
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
                error=error,
                image_attached=image_attached,
                image_url=image_url,
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
        account_key: Optional[str] = None,
        user_key: Optional[str] = None,
        endpoint: str = None,
    ) -> Dict[str, Any]:
        """Send a single query to OpenAI.

        Args:
            prompt: The user's query
            model: Model to use (default from config)
            max_tokens: Maximum tokens in response
            temperature: Creativity (0-2, default 0.7)
            system_prompt: Optional system context
            account_key: Account key for usage tracking
            user_key: User key for usage tracking
            endpoint: API endpoint for usage tracking

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        result = self._chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Log usage if account_key provided
        if account_key and result.get('usage'):
            self._log_usage(
                account_key=account_key,
                user_key=user_key or 'unknown',
                tokens=result['usage'],
                model=result.get('model'),
                endpoint=endpoint or '/ai/openai/query',
                success=True
            )

        return result

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        account_key: Optional[str] = None,
        user_key: Optional[str] = None,
        endpoint: str = None,
    ) -> Dict[str, Any]:
        """Multi-turn chat conversation.

        Args:
            messages: List of message dicts with role and content
            model: Model to use
            max_tokens: Maximum tokens
            temperature: Creativity
            account_key: Account key for usage tracking
            user_key: User key for usage tracking
            endpoint: API endpoint for usage tracking

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        result = self._chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Log usage if account_key provided
        if account_key and result.get('usage'):
            self._log_usage(
                account_key=account_key,
                user_key=user_key or 'unknown',
                tokens=result['usage'],
                model=result.get('model'),
                endpoint=endpoint or '/ai/openai/chat',
                success=True
            )

        return result

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
    # Image Analysis Methods (Vision API)
    # =========================================================================

    def analyze_image(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "What's in this image?",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        account_key: Optional[str] = None,
        user_key: Optional[str] = None,
        detail: str = "auto",
    ) -> Dict[str, Any]:
        """Analyze an image using OpenAI Vision.

        Args:
            image_url: URL of the image to analyze
            image_base64: Base64 encoded image data
            prompt: Question or instruction about the image
            model: Model to use (must support vision, e.g., gpt-4o, gpt-4o-mini)
            max_tokens: Maximum tokens in response
            account_key: Account key for usage tracking
            user_key: User key for usage tracking
            detail: Image detail level - "low", "high", or "auto"

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        if not image_url and not image_base64:
            raise ValueError("Either image_url or image_base64 is required")

        # Build image content
        if image_url:
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": detail,
                }
            }
        else:
            # Determine image type from base64 header or default to jpeg
            if image_base64.startswith('/9j/'):
                mime_type = "image/jpeg"
            elif image_base64.startswith('iVBOR'):
                mime_type = "image/png"
            elif image_base64.startswith('R0lG'):
                mime_type = "image/gif"
            elif image_base64.startswith('UklGR'):
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_base64}",
                    "detail": detail,
                }
            }

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_content,
                ]
            }
        ]

        # Use vision-capable model
        vision_model = model or self._default_model
        # Ensure model supports vision
        if vision_model not in ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4-vision-preview']:
            vision_model = 'gpt-4o-mini'  # Default to gpt-4o-mini which supports vision

        result = self._chat_completion(
            messages=messages,
            model=vision_model,
            max_tokens=max_tokens or 1000,
        )

        # Log usage
        if account_key and result.get('usage'):
            self._log_usage(
                account_key=account_key,
                user_key=user_key or 'unknown',
                tokens=result['usage'],
                model=result.get('model'),
                endpoint='/ai/openai/analyze-image',
                success=True,
                image_attached=True,
                image_url=image_url,  # Will be None if base64 was used
            )

        return result

    def analyze_multiple_images(
        self,
        images: List[Dict[str, str]],
        prompt: str = "Analyze these images",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        account_key: Optional[str] = None,
        user_key: Optional[str] = None,
        detail: str = "auto",
    ) -> Dict[str, Any]:
        """Analyze multiple images together.

        Args:
            images: List of dicts with either 'url' or 'base64' key
            prompt: Question or instruction about the images
            model: Model to use
            max_tokens: Maximum tokens in response
            account_key: Account key for usage tracking
            user_key: User key for usage tracking
            detail: Image detail level

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not self.is_configured():
            raise ValueError("OpenAI is not configured")

        if not images:
            raise ValueError("At least one image is required")

        content = [{"type": "text", "text": prompt}]

        for img in images:
            if 'url' in img:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img['url'], "detail": detail}
                })
            elif 'base64' in img:
                base64_data = img['base64']
                mime_type = img.get('mime_type', 'image/jpeg')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_data}",
                        "detail": detail
                    }
                })

        messages = [{"role": "user", "content": content}]

        vision_model = model or 'gpt-4o-mini'

        result = self._chat_completion(
            messages=messages,
            model=vision_model,
            max_tokens=max_tokens or 2000,
        )

        if account_key and result.get('usage'):
            # Collect image URLs if any provided via URL
            image_urls = [img.get('url') for img in images if img.get('url')]
            self._log_usage(
                account_key=account_key,
                user_key=user_key or 'unknown',
                tokens=result['usage'],
                model=result.get('model'),
                endpoint='/ai/openai/analyze-images',
                success=True,
                image_attached=True,
                image_url=','.join(image_urls) if image_urls else None,  # Store comma-separated URLs
            )

        return result

    def analyze_fish_image(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        analysis_type: str = "general",
        account_key: Optional[str] = None,
        user_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Specialized fish image analysis.

        Args:
            image_url: URL of the fish image
            image_base64: Base64 encoded image
            analysis_type: Type of analysis - "general", "health", "species", "size"
            account_key: Account key for usage tracking
            user_key: User key for usage tracking

        Returns:
            Dict with analysis results
        """
        prompts = {
            "general": """Analyze this fish farm image. Describe:
1. What type of fish you see (if visible)
2. Approximate number of fish
3. Water clarity and color
4. Any visible health issues or concerns
5. Overall condition assessment""",

            "health": """Analyze this fish image for health indicators:
1. Body condition and shape
2. Fin condition (any damage, rot, or abnormalities)
3. Scale condition
4. Eye clarity and condition
5. Any visible lesions, spots, or parasites
6. Swimming behavior if visible
7. Overall health score (1-10) with explanation""",

            "species": """Identify the fish species in this image:
1. Most likely species identification
2. Confidence level
3. Key identifying features observed
4. Similar species it could be confused with
5. Typical characteristics of this species""",

            "size": """Estimate the size and weight of fish in this image:
1. Estimated length (cm)
2. Estimated weight (grams/kg)
3. Growth stage (fry, fingerling, juvenile, adult)
4. Body condition factor estimation
5. Comparison to typical size for the species (if identifiable)""",
        }

        prompt = prompts.get(analysis_type, prompts["general"])

        system_context = """You are an expert aquaculture and fisheries specialist with extensive knowledge of:
- Fish species identification
- Fish health assessment
- Aquaculture practices
- Water quality indicators
- Common fish diseases and conditions

Provide detailed, professional analysis based on what you can observe in the image."""

        result = self.analyze_image(
            image_url=image_url,
            image_base64=image_base64,
            prompt=f"{system_context}\n\n{prompt}",
            account_key=account_key,
            user_key=user_key,
            detail="high",  # Use high detail for fish analysis
        )

        return {
            "analysis_type": analysis_type,
            "content": result.get("content"),
            "model": result.get("model"),
            "usage": result.get("usage"),
        }

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

