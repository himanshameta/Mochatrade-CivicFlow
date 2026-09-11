"""
CivicFlow — Unified LLM Helper
===============================
Single interface for all LLM calls using OpenRouter.
Replaces all Gemini usage throughout the project.
"""
import os
import json
import httpx
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("civicflow.llm")


class LLMClient:
    """Unified LLM client using OpenRouter API with fallback models."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
        self.timeout = 30.0
        self.fallback_models = [
            "meta-llama/llama-3-8b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemma-2-9b-it:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-medium-128k-instruct:free"
        ]
        
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate content from a prompt, trying fallback models if the main one fails.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        
        last_error = None
        for model in models_to_try:
            logger.info(f"Attempting LLM generation with model: {model}")
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://civicflow.app",
                            "X-Title": "CivicFlow"
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }
                    )
                    
                    if response.status_code != 200:
                        error_text = response.text
                        logger.error(f"OpenRouter API error for model {model}: {response.status_code} - {error_text}")
                        raise Exception(f"OpenRouter API error: {response.status_code}")
                    
                    result = response.json()
                    
                    if "error" in result:
                        raise Exception(result["error"].get("message", "Unknown error"))
                    
                    content = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"Successfully generated content using model: {model}")
                    return content
                    
            except httpx.TimeoutException as e:
                logger.error(f"OpenRouter request timeout for model {model}")
                last_error = e
            except Exception as e:
                logger.error(f"LLM call failed for model {model}: {e}")
                last_error = e
                
        raise Exception(f"All LLM models failed. Last error: {last_error}")



# Global singleton
_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
