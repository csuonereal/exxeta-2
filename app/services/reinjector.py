from typing import Dict

class ReinjectorService:
    @staticmethod
    def reinject(abstracted_output: str, mapping: Dict[str, dict]) -> str:
        final_output = abstracted_output
        
        # Standard replace loops over the exact keys
        # E.g. <PERSON_1> -> John Doe
        for placeholder, entity_data in mapping.items():
            original_value = entity_data["value"]
            final_output = final_output.replace(placeholder, original_value)
            
        return final_output
