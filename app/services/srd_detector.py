import httpx
import json
from app.config import config
import re

class SRDDetectorService:
    def __init__(self):
        self.host = config.OLLAMA_HOST
        self.model = config.OLLAMA_SRD_MODEL

    async def detect_entities(self, text: str) -> list[dict]:
        # Direct regex for common patterns as a fallback/fast-path
        # But per requirements, use local LLM mapping if possible, or rule-based.
        # For this MVP, we prompt Ollama to give us a JSON of entities.
        
        prompt = f"""
        Identify Sensitive Regulated Data (SRD) in the following text. 
        Focus strictly on: Names of people (PERSON), Organizations (ORG), Emails (EMAIL), and Financial Data (FINANCE).
        Output ONLY a valid JSON list of objects, where each object has 'value' (the exact text snippet) and 'type' (the category). Do not write ANY markdown formatting.
        Example: [{{"value": "John Doe", "type": "PERSON"}}]

        Text:
        {text}
        """

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    },
                    timeout=60.0
                )
                if res.status_code == 200:
                    response_text = res.json().get("response", "[]")
                    # In case LLM returns markdown blocks
                    clean_text = re.sub(r'```json|```', '', response_text).strip()
                    try:
                        entities = json.loads(clean_text)
                        if isinstance(entities, list):
                            return entities
                        elif isinstance(entities, dict) and "srd_entities" in entities:
                            return entities["srd_entities"]
                    except json.JSONDecodeError as de:
                        print(f"JSON Parse error. Raw output: {clean_text}")
        except Exception as e:
            print(f"SRD Detection local LLM failed, fallback to rules: {str(e)}")
            pass
        
        # Fallback to regex if LLM fails or is slow
        return self._regex_fallback(text)
        
    def _regex_fallback(self, text: str) -> list[dict]:
        entities = []
        # Basic email fallback
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        for email in emails:
            entities.append({"value": email, "type": "EMAIL"})
        return entities
