"""
LLM Provider abstraction for RAG system.

Supports multiple backends:
1. AWS Bedrock (Claude, Mistral, etc)
2. Ollama (local models)

Design allows easy switching between providers without changing application code.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass
import time


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    text: str
    model: str
    provider: str

    # Metadata
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: float = 0

    # Cost estimation (optional)
    cost_usd: Optional[float] = None

    # Raw response for debugging
    raw_response: Optional[Dict] = None

    def __repr__(self):
        return f"LLMResponse(model={self.model}, tokens={self.tokens_input}→{self.tokens_output}, latency={self.latency_ms:.0f}ms)"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text from prompt.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = deterministic)
            **kwargs: Provider-specific arguments

        Returns:
            LLMResponse object
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Generate text with streaming (for real-time UX).

        Yields text chunks as they're generated.
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text (approximate for non-native providers)."""
        pass


# Default models (tested and working) - defined before classes
DEFAULT_BEDROCK_MODEL = 'us.anthropic.claude-sonnet-4-6'  # Claude Sonnet 4.6 via inference profile
DEFAULT_OLLAMA_MODEL = 'llama3.1:8b'


class BedrockProvider(LLMProvider):
    """
    AWS Bedrock LLM provider.

    Supports Claude, Mistral, Llama models available in Bedrock.

    Setup:
        - Requires AWS credentials configured (via aws configure or env vars)
        - Requires bedrock access in the AWS account

    Example:
        provider = BedrockProvider(model_id='anthropic.claude-sonnet-4-6')
        response = provider.generate("Explain quantum computing")
    """

    def __init__(
        self,
        model_id: str = DEFAULT_BEDROCK_MODEL,
        region: str = 'us-east-1'
    ):
        """
        Initialize Bedrock provider.

        Args:
            model_id: Bedrock model ID or inference profile
                Recommended inference profiles (tested and working):
                - us.anthropic.claude-sonnet-4-6 (best quality, default)
                - us.anthropic.claude-haiku-4-5-20251001-v1:0 (fast, cheap)
                - us.anthropic.claude-sonnet-4-5-20250929-v1:0 (balanced)

                Legacy direct model IDs (also work):
                - anthropic.claude-3-sonnet-20240229-v1:0
                - mistral.mixtral-8x7b-instruct-v0:1 (fast)
            region: AWS region
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 not installed. Install with: pip install boto3"
            )

        self.model_id = model_id
        self.region = region

        # Detect provider name - handle inference profiles (us.anthropic.xxx) and direct IDs (anthropic.xxx)
        if '.' in model_id:
            parts = model_id.split('.')
            # If starts with region prefix (us, eu, global), provider is second part
            if parts[0] in ['us', 'eu', 'global']:
                self.provider_name = parts[1]  # 'anthropic' from 'us.anthropic.claude-sonnet-4-6'
            else:
                self.provider_name = parts[0]  # 'anthropic' from 'anthropic.claude-3-sonnet...'
        else:
            self.provider_name = 'anthropic'  # Default for simple names

        # Initialize bedrock client
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=region
        )

        print(f"✓ Bedrock provider initialized: {model_id} ({region})")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> LLMResponse:
        """Generate text via Bedrock."""

        start_time = time.time()

        # Build request body (format depends on provider)
        if self.provider_name == 'anthropic':
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Optional parameters
            if 'system' in kwargs:
                body['system'] = kwargs['system']
            if 'stop_sequences' in kwargs:
                body['stop_sequences'] = kwargs['stop_sequences']

        elif self.provider_name == 'mistral':
            body = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

        # Call Bedrock
        import json

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())

        latency_ms = (time.time() - start_time) * 1000

        # Extract text and metadata (format depends on provider)
        if self.provider_name == 'anthropic':
            text = response_body['content'][0]['text']
            tokens_input = response_body['usage']['input_tokens']
            tokens_output = response_body['usage']['output_tokens']

            # Cost estimation (Claude Sonnet 4.6 pricing)
            cost_usd = (tokens_input / 1_000_000 * 3.0) + \
                       (tokens_output / 1_000_000 * 15.0)

        elif self.provider_name == 'mistral':
            text = response_body['outputs'][0]['text']
            tokens_input = response_body.get('usage', {}).get('prompt_tokens')
            tokens_output = response_body.get('usage', {}).get('completion_tokens')
            cost_usd = None  # TODO: add Mistral pricing

        else:
            text = str(response_body)  # Fallback
            tokens_input = None
            tokens_output = None
            cost_usd = None

        return LLMResponse(
            text=text,
            model=self.model_id,
            provider='bedrock',
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            raw_response=response_body
        )

    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> Generator[str, None, None]:
        """Generate with streaming (Bedrock streaming API)."""

        # Build request body
        if self.provider_name == 'anthropic':
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            if 'system' in kwargs:
                body['system'] = kwargs['system']
        else:
            raise NotImplementedError(f"Streaming not implemented for {self.provider_name}")

        import json

        # Call streaming API
        response = self.client.invoke_model_with_response_stream(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        # Stream chunks
        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'])

            if chunk['type'] == 'content_block_delta':
                if 'delta' in chunk and 'text' in chunk['delta']:
                    yield chunk['delta']['text']

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count.

        Note: This is approximate. For exact count, need to call tokenizer API.
        Claude approximation: ~4 chars per token for English/Portuguese.
        """
        return len(text) // 4


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider (local models).

    Ollama allows running models like Llama 3, Mistral, Qwen locally.

    Setup:
        1. Install Ollama: https://ollama.ai
        2. Pull model: ollama pull llama3.1:8b
        3. Start server: ollama serve (runs on http://localhost:11434)

    Example:
        provider = OllamaProvider(model='llama3.1:8b')
        response = provider.generate("Explain quantum computing")

    Recommended models for Portuguese RAG:
        - llama3.1:8b (fast, good quality)
        - llama3.1:70b (best quality, requires GPU)
        - mistral:7b (fast, good for Portuguese)
        - qwen2.5:7b (good multilingual)
    """

    def __init__(
        self,
        model: str = 'llama3.1:8b',
        base_url: str = 'http://localhost:11434'
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (e.g., 'llama3.1:8b', 'mistral:7b')
            base_url: Ollama server URL
        """
        self.model = model
        self.base_url = base_url

        # Test connection
        import requests

        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()

            # Check if model is available
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if model not in model_names:
                print(f"⚠️  Model '{model}' not found in Ollama.")
                print(f"   Available models: {model_names}")
                print(f"   Pull with: ollama pull {model}")
            else:
                print(f"✓ Ollama provider initialized: {model} ({base_url})")

        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {base_url}. "
                f"Make sure Ollama is running: ollama serve\n"
                f"Error: {e}"
            )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> LLMResponse:
        """Generate text via Ollama."""

        import requests
        import json

        start_time = time.time()

        # Build request
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens  # Ollama uses num_predict instead of max_tokens
            }
        }

        # Optional system prompt
        if 'system' in kwargs:
            data['system'] = kwargs['system']

        # Call Ollama API
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=data,
            timeout=120  # Ollama can be slow on CPU
        )
        response.raise_for_status()

        result = response.json()

        latency_ms = (time.time() - start_time) * 1000

        # Parse response
        text = result['response']

        # Token counts (Ollama provides these)
        tokens_input = result.get('prompt_eval_count')
        tokens_output = result.get('eval_count')

        # Cost is zero (local model)
        cost_usd = 0.0

        return LLMResponse(
            text=text,
            model=self.model,
            provider='ollama',
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            raw_response=result
        )

    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        **kwargs
    ) -> Generator[str, None, None]:
        """Generate with streaming."""

        import requests
        import json

        # Build request
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        if 'system' in kwargs:
            data['system'] = kwargs['system']

        # Stream response
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=data,
            stream=True,
            timeout=120
        )
        response.raise_for_status()

        # Yield chunks
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if 'response' in chunk:
                    yield chunk['response']

                # Check if done
                if chunk.get('done', False):
                    break

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count.

        Llama tokenizer approximation: ~4 chars per token.
        For exact count, would need to use transformers tokenizer.
        """
        return len(text) // 4


def create_llm_provider(
    provider_type: str = 'bedrock',
    **kwargs
) -> LLMProvider:
    """
    Factory function to create LLM provider.

    Args:
        provider_type: 'bedrock' or 'ollama'
        **kwargs: Provider-specific arguments

    Returns:
        LLMProvider instance

    Examples:
        # Bedrock
        provider = create_llm_provider('bedrock', model_id='anthropic.claude-sonnet-4-6')

        # Ollama
        provider = create_llm_provider('ollama', model='llama3.1:8b')

        # From environment variable
        import os
        provider_type = os.getenv('LLM_PROVIDER', 'bedrock')
        provider = create_llm_provider(provider_type)
    """

    if provider_type.lower() == 'bedrock':
        model_id = kwargs.get('model_id', DEFAULT_BEDROCK_MODEL)
        region = kwargs.get('region', 'us-east-1')
        return BedrockProvider(model_id=model_id, region=region)

    elif provider_type.lower() == 'ollama':
        model = kwargs.get('model', 'llama3.1:8b')
        base_url = kwargs.get('base_url', 'http://localhost:11434')
        return OllamaProvider(model=model, base_url=base_url)

    else:
        raise ValueError(
            f"Unknown provider type: {provider_type}. "
            f"Supported: 'bedrock', 'ollama'"
        )


# Model recommendations for different scenarios
# Based on actual testing with available access (May 2026)
RECOMMENDED_MODELS = {
    'bedrock': {
        # Claude 4.x via inference profiles (tested and working)
        'best_quality': 'us.anthropic.claude-sonnet-4-6',  # Sonnet 4.6, best quality
        'fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',  # Haiku 4.5, fast and cheap
        'balanced': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',  # Sonnet 4.5, balanced
        'cheap': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',  # Same as fast

        # Alternative providers via inference profiles
        'mistral_fast': 'mistral.mixtral-8x7b-instruct-v0:1',  # Tested: 4x faster than Claude 3
        'llama': 'us.meta.llama3-3-70b-instruct-v1:0',
        'deepseek': 'us.deepseek.r1-v1:0',
        'opus': 'us.anthropic.claude-opus-4-20250514-v1:0',  # Claude Opus 4 (most capable)

        # Legacy Claude 3.x (also work with direct model IDs)
        'claude3_sonnet': 'anthropic.claude-3-sonnet-20240229-v1:0',
        'claude3_haiku': 'anthropic.claude-3-haiku-20240307-v1:0',
    },
    'ollama': {
        'best_quality': 'llama3.1:70b',  # Requires GPU
        'fast': 'llama3.1:8b',
        'balanced': 'mistral:7b',
        'cheap': 'llama3.1:8b',  # Free (local)
        'multilingual': 'qwen2.5:7b',
    }
}
