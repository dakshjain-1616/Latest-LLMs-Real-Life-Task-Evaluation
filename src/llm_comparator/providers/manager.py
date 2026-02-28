import os
import time
import asyncio
import logging
import json
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import yaml
from openai import AsyncOpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ModelResponse:
    """Standardized response format from any model."""
    model_output: str
    tokens_prompt: int
    tokens_completion: int
    tokens_used: int
    latency_ms: float
    cost_usd: float
    error: Optional[str] = None
    provider: str = ""
    model_name: str = ""

class ProviderManager:
    """Unified manager for various LLM providers supporting multi-key authentication."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Try to find config relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.config_path = os.path.join(base_dir, "llm_comparator/config/models.yaml")
        else:
            self.config_path = config_path
        
        self.models_registry = self._load_registry()
        self.clients = {}
        
    def _load_registry(self) -> Dict[str, Any]:
        """Load model registry from config file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config path {self.config_path} not found. Using empty registry.")
            return {"models": {}, "active_models": []}
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _get_client(self, provider: str) -> Any:
        """Get or initialize the appropriate client for the provider."""
        if provider in self.clients:
            return self.clients[provider]
        
        api_key = None
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            client = AsyncOpenAI(api_key=api_key)
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                logger.warning("OPENROUTER_API_KEY not found in environment.")
            
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/dakshjain-1616/Latest-LLMs-Real-Life-Task-Evaluation",
                    "X-Title": "LLM Comparison Tool",
                }
            )

        elif provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
            # Using Google's OpenAI-compatible endpoint
            client = AsyncOpenAI(
                api_key=api_key, 
                base_url="https://generativelanguage.googleapis.com/v1beta/openai"
            )
        elif provider == "zhipuai":
            api_key = os.getenv("ZHIPU_API_KEY")
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            client = httpx.AsyncClient(base_url="https://api.anthropic.com/v1")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        if not api_key and provider != "anthropic":
            # Anthropic check is internal to the call
            logger.warning(f"API key for {provider} not found in environment. Calls may fail.")

        self.clients[provider] = client
        return client

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get model metadata from the registry."""
        for provider, models in self.models_registry.get("models", {}).items():
            for m in models:
                if m.get("name") == model_name or m.get("model_id") == model_name:
                    m["provider"] = provider
                    return m
        return None

    async def _call_anthropic_native(self, client: httpx.AsyncClient, model_id: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Native call to Anthropic Messages API."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": model_id,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.0)
        }
        response = await client.post("/messages", headers=headers, json=data, timeout=120.0)
        response.raise_for_status()
        res_json = response.json()
        
        return {
            "content": res_json["content"][0]["text"],
            "prompt_tokens": res_json["usage"]["input_tokens"],
            "completion_tokens": res_json["usage"]["output_tokens"]
        }

    async def call_model(self, model_name: str, prompt: str, system_prompt: str = "", **kwargs) -> ModelResponse:
        """Call a model and return a standardized response."""
        model_info = self.get_model_info(model_name)
        if not model_info:
            logger.info(f"Model {model_name} not found in registry. Defaulting to OpenRouter.")
            model_info = {"model_id": model_name, "provider": "openrouter"}

        provider = model_info["provider"]
        model_id = model_info["model_id"]
        client = self._get_client(provider)
        
        start_time = time.perf_counter()
        try:
            if provider == "anthropic":
                res = await self._call_anthropic_native(client, model_id, prompt, **kwargs)
                content = res["content"]
                prompt_tokens = res["prompt_tokens"]
                completion_tokens = res["completion_tokens"]
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    **kwargs
                )
                content = response.choices[0].message.content
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            latency_ms = (time.perf_counter() - start_time) * 1000
            pricing = model_info.get("pricing", {"prompt_per_1k": 0.0, "completion_per_1k": 0.0})
            cost_usd = (prompt_tokens * pricing.get("prompt_per_1k", 0) / 1000) + \
                       (completion_tokens * pricing.get("completion_per_1k", 0) / 1000)

            return ModelResponse(
                model_output=content,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens,
                tokens_used=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                provider=provider,
                model_name=model_name
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Error calling model {model_name}: {str(e)}")
            return ModelResponse(
                model_output="", tokens_prompt=0, tokens_completion=0, tokens_used=0,
                latency_ms=latency_ms, cost_usd=0.0, error=str(e),
                provider=provider, model_name=model_name
            )
