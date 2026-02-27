import asyncio
import os
from llm_comparator.providers.manager import ProviderManager

async def test_routing():
    """Verify that models are correctly routed to their providers."""
    manager = ProviderManager()
    
    # List of models to test from models.yaml active_models
    test_models = [
        "gemini-3.1-pro-or",
        "glm-5-native",
        "claude-4.6-opus-native",
        "claude-4.6-sonnet-or",
        "gpt-4o-native"
    ]
    
    print("--- Model Routing Verification ---")
    for name in test_models:
        info = manager.get_model_info(name)
        if info:
            print(f"Model: {name}")
            print(f"  Provider: {info['provider']}")
            print(f"  Model ID: {info['model_id']}")
        else:
            print(f"Model: {name} NOT FOUND in registry.")
    
    print("\n--- Client Initialization Test (Dry Run) ---")
    for provider in ["openai", "openrouter", "google", "zhipuai", "anthropic"]:
        try:
            client = manager._get_client(provider)
            print(f"Provider {provider}: Client initialized successfully.")
        except Exception as e:
            print(f"Provider {provider}: Initialization FAILED - {e}")

if __name__ == "__main__":
    # Mock some keys for initialization test if missing
    os.environ.setdefault("OPENAI_API_KEY", "mock-key")
    os.environ.setdefault("OPENROUTER_API_KEY", "mock-key")
    os.environ.setdefault("GOOGLE_API_KEY", "mock-key")
    os.environ.setdefault("ZHIPU_API_KEY", "mock-key")
    os.environ.setdefault("ANTHROPIC_API_KEY", "mock-key")
    
    asyncio.run(test_routing())
