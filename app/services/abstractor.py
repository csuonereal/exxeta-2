from typing import Tuple, Dict

class AbstractorService:
    @staticmethod
    def abstract_text(text: str, entities: list[dict]) -> Tuple[str, Dict[str, dict]]:
        mapping = {}
        abstracted_text = text
        
        # Sort entities by length descending to avoid partial replacements
        unique_entities = {e["value"]: e["type"] for e in entities}
        sorted_values = sorted(unique_entities.keys(), key=len, reverse=True)
        
        counters = {"PERSON": 1, "ORG": 1, "EMAIL": 1, "FINANCE": 1, "OTHER": 1}
        
        for value in sorted_values:
            etype = unique_entities[value]
            # Ensure type is known, else fallback
            if etype not in counters:
                etype = "OTHER"
                
            placeholder = f"<{etype}_{counters[etype]}>"
            counters[etype] += 1
            
            # Map specific placeholder to exact value
            mapping[placeholder] = {"value": value, "type": etype}
            
            # Simple replace (Note: in production use word boundaries re.sub(r'\b'+value+r'\b'))
            abstracted_text = abstracted_text.replace(value, placeholder)
            
        return abstracted_text, mapping
