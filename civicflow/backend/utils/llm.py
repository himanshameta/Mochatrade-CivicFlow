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
    """Unified LLM client using OpenRouter API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.timeout = 30.0
        
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate content from a prompt.
        
        Args:
            prompt: User prompt
            system_instruction: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
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
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
                    raise Exception(f"OpenRouter API error: {response.status_code}")
                
                result = response.json()
                
                if "error" in result:
                    raise Exception(result["error"].get("message", "Unknown error"))
                
                return result["choices"][0]["message"]["content"].strip()
                
        except httpx.TimeoutException:
            logger.error("OpenRouter request timeout")
            raise Exception("LLM request timeout")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


# Global singleton
_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
