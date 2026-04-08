import httpx
from app.config import config
import openai
import os
from google import genai
from anthropic import AsyncAnthropic

class LLMGatewayService:
    def __init__(self):
        self.ollama_host = config.OLLAMA_HOST
        self.ollama_model = config.OLLAMA_ROUTING_MODEL
        
        # Setup clients conditionally
        if config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        else:
            self.openai_client = None
            
        if config.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        else:
            self.anthropic_client = None
            
        if config.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        else:
            self.gemini_client = None

    async def process(self, prompt: str, route: str, user_model_pref: str) -> str:
        if route == "BLOCK":
            return "Request blocked by compliance layer."
            
        if route == "LOCAL" or user_model_pref == "local":
            return await self._call_ollama(prompt)
            
        # Defaults to HYBRID (Remote Proprietary)
        if user_model_pref == "openai" and self.openai_client:
            return await self._call_openai(prompt)
        elif user_model_pref == "anthropic" and self.anthropic_client:
            return await self._call_anthropic(prompt)
        elif user_model_pref == "gemini" and self.gemini_client:
             return await self._call_gemini(prompt)
             
        # Fallback to local if no API keys are provided for hybrid
        if not self.openai_client and not self.anthropic_client and not self.gemini_client:
            print("Warning: HYBRID requested but no remote API keys configured. Falling back to LOCAL.")
            return await self._call_ollama(prompt)
            
        # Default fallback to OpenAI if available
        if self.openai_client:
            return await self._call_openai(prompt)
            
        return await self._call_ollama(prompt)

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60.0
            )
            if res.status_code == 200:
                return res.json().get("response", "")
            return f"Ollama Error: {res.status_code}"

    async def _call_openai(self, prompt: str) -> str:
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    async def _call_anthropic(self, prompt: str) -> str:
        message = await self.anthropic_client.messages.create(
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            model="claude-3-haiku-20240307",
        )
        return message.content[0].text
        
    async def _call_gemini(self, prompt: str) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        def _call_sync():
            return self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
        response = await loop.run_in_executor(None, _call_sync)
        return response.text
