from typing import Tuple

class PolicyRouterService:
    @staticmethod
    def evaluate_route(srd_count: int, domain_task: str) -> Tuple[str, str, str]:
        """
        Returns: risk_level, route, explanation
        """
        # Hard policy definitions (mocked for MVP)
        prohibited_keywords = ["medical_diagnosis", "credit_card_processing", "top_secret"]
        
        # Check prohibited list
        for word in prohibited_keywords:
            if word in domain_task.lower():
                return "PROHIBITED", "BLOCK", f"Hard policy violation: task '{domain_task}' is strictly prohibited."
                
        # Evaluated purely on SRD count for MVP
        if srd_count == 0:
            return "MINIMAL", "HYBRID", "No sensitive data detected. Safe to route to proprietary API."
        elif srd_count <= 5:
            return "LIMITED", "HYBRID", f"{srd_count} sensitive entities tracked and abstracted. Safe to route to proprietary API."
        else:
            return "HIGH", "LOCAL", f"High volume ({srd_count}) of sensitive data detected. Hard policy: FORCE_LOCAL routing to prevent bulk leakage."
