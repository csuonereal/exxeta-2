from app.services.parser import ParserService
from app.services.srd_detector import SRDDetectorService
from app.services.abstractor import AbstractorService
from app.services.policy_router import PolicyRouterService
from app.services.llm_gateway import LLMGatewayService
from app.services.reinjector import ReinjectorService
from app.services.judge import JudgeService
from app.schemas.requests import ProcessRequest
from app.schemas.responses import ProcessResponse, JudgeDetails
import hashlib

class OrchestratorService:
    def __init__(self):
        self.srd_detector = SRDDetectorService()
        self.llm_gateway = LLMGatewayService()
        self.judge = JudgeService()

    async def run_pipeline(self, raw_req: ProcessRequest) -> dict:
        # 1. Parse Input
        raw_text = ParserService.parse_input(raw_req.input_type, raw_req.content)
        input_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()
        
        # 2. SRD Detection
        entities = await self.srd_detector.detect_entities(raw_text)
        srd_count = len(entities)
        
        # 3. Context Abstraction
        abstracted_text, mapping = AbstractorService.abstract_text(raw_text, entities)
        
        # 4. Policy & Routing
        risk_level, route_decision, explanation = PolicyRouterService.evaluate_route(srd_count, raw_req.task)
        
        # Combine task and abstracted text
        llm_prompt = f"Task: {raw_req.task}\n\nInput Context:\n{abstracted_text}"
        
        # 5. Model Abstraction Layer Execution
        generated_output = await self.llm_gateway.process(llm_prompt, route_decision, raw_req.model_pref)
        
        # 6. Reinjection
        if route_decision != "BLOCK":
            final_output = ReinjectorService.reinject(generated_output, mapping)
        else:
            final_output = generated_output
            
        # 7. Judge Model Verification
        judge_res = await self.judge.evaluate(raw_text, final_output)
        
        # Determine actual model used for logging logic (mocked logic)
        actual_model = raw_req.model_pref if route_decision != "LOCAL" else "local_ollama"
        if route_decision == "BLOCK": actual_model = "NONE"

        return {
            "output": final_output,
            "risk_level": risk_level,
            "route": route_decision,
            "explanation": explanation,
            "judge": judge_res,
            "srd_count": srd_count,
            "input_hash": input_hash,
            "model_used": actual_model
        }
