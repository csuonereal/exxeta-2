import httpx
import json
from app.config import config
import re

# We install presidio_analyzer, catching imports gracefully to not crash if uninstalled yet
try:
    from presidio_analyzer import AnalyzerEngine
except ImportError:
    AnalyzerEngine = None

# Singleton to prevent massive loading lags on every API hit
_analyzer_engine = None

class SRDDetectorService:
    def __init__(self):
        global _analyzer_engine
        if AnalyzerEngine and _analyzer_engine is None:
            _analyzer_engine = AnalyzerEngine()
        self.analyzer = _analyzer_engine

    async def detect_entities(self, text: str) -> list[dict]:
        # If Presidio installed correctly, leverage it
        if self.analyzer:
            try:
                results = self.analyzer.analyze(
                    text=text,
                    entities=["PERSON", "CREDIT_CARD", "US_BANK_NUMBER", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "DATE_TIME"],
                    language="en"
                )
                
                entities = []
                for res in results:
                    entity_value = text[res.start:res.end]
                    # Map to generic tags so our Abstractor/Reinjector doesn't break
                    etype = res.entity_type
                    if etype == "EMAIL_ADDRESS":
                        etype = "EMAIL"
                    elif etype in ["CREDIT_CARD", "US_BANK_NUMBER", "US_SSN"]:
                        etype = "FINANCE"
                        
                    entities.append({
                        "value": entity_value,
                        "type": etype,
                    })
                return entities

            except Exception as e:
                print(f"Presidio crash, fallback rules: {str(e)}")

        # Hard Fallback
        return self._regex_fallback(text)
        
    def _regex_fallback(self, text: str) -> list[dict]:
        entities = []
        # Basic email fallback
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        for email in emails:
            entities.append({"value": email, "type": "EMAIL"})
        return entities
