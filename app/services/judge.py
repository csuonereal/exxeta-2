import httpx
from app.config import config
import json
import re

class JudgeService:
    def __init__(self):
        self.host = config.OLLAMA_HOST
        self.model = config.OLLAMA_JUDGE_MODEL

    async def evaluate(self, original_prompt: str, final_output: str) -> dict:
        """
        Returns a dict: {"status": "APPROVED" | "FLAGGED" | "BLOCKED", "reasoning": "..."}
        """
        prompt = f"""
        You are a compliance judge. Review the following AI output for any sensitive data leakage or harmful content.
        Original Prompt Snippet: {original_prompt[:200]}...
        Final Output:
        {final_output}
        
        Evaluate if the final output contains obvious unmasked sensitive data (like real credit cards, SSNs) that shouldn't be there, or harmful content.
        Respond ONLY with a JSON object containing "status" (which must be exactly "APPROVED", "FLAGGED", or "BLOCKED") and "reasoning" (a brief string explaining why). Do not use markdown blocks.
        """
        
        fallback_res = {"status": "APPROVED", "reasoning": "Judge unreachable or failed. Defaulting to APPROVED to maintain availability."}
        
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
                    response_text = res.json().get("response", "{}")
                    clean_text = re.sub(r'```json|```', '', response_text).strip()
                    try:
                        judge_result = json.loads(clean_text)
                        if "status" in judge_result and "reasoning" in judge_result:
                            status = judge_result["status"].upper()
                            if status not in ["APPROVED", "FLAGGED", "BLOCKED"]:
                                status = "FLAGGED"
                            judge_result["status"] = status
                            return judge_result
                    except json.JSONDecodeError as de:
                        print(f"JSON Parse error in Judge. Raw output: {clean_text}")
        except Exception as e:
            print(f"Judge local LLM failed: {str(e)}")
            
        return fallback_res
