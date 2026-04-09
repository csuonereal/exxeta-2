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
import json

class OrchestratorService:
    def __init__(self):
        self.srd_detector = SRDDetectorService()
        self.llm_gateway = LLMGatewayService()
        self.judge = JudgeService()

    async def run_pipeline_stream(self, raw_req: ProcessRequest):
        # Helper to format SSE events
        def format_event(step: str, title: str, details: str = ""):
            payload = json.dumps({'step': step, 'title': title, 'details': details})
            return f"data: {payload}\n\n"

        # 1. Parse Input
        yield format_event("parsing", "Parsing context...")
        content_to_parse = raw_req.file_data if raw_req.file_data else raw_req.content
        input_type = "pdf" if raw_req.file_name and raw_req.file_name.endswith('.pdf') else raw_req.input_type
        
        raw_text = ParserService.parse_input(input_type, content_to_parse)
        # Merge task/content context if files are provided
        if raw_req.file_data and raw_req.content:
             raw_text = f"User Request: {raw_req.content}\n\nDocument Context:\n{raw_text}"
             
        input_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()
        yield f"data: {json.dumps({'step': 'hash', 'hash': input_hash})}\n\n"
        
        # 2. SRD Detection
        yield format_event("srd", "Detecting Sensitive Regulated Data...")
        entities = await self.srd_detector.detect_entities(raw_text)
        srd_count = len(entities)
        yield format_event("srd_done", "SRD Detection Complete", f"Found {srd_count} tracking entities.")
        
        # 3. Context Abstraction
        abstracted_text, mapping = AbstractorService.abstract_text(raw_text, entities)
        
        # 4. Policy & Routing
        risk_level, route_decision, explanation = PolicyRouterService.evaluate_route(srd_count, raw_req.task or "")
        yield format_event("route", f"Risk: {risk_level} | Route: {route_decision}", explanation)
        
        # Combine task and abstracted text gracefully
        adaptive_instruction = "\n\nCRITICAL INSTRUCTION: If the user asks you to rewrite, draft, modify, or update a document, you MUST wrap your proposed new content precisely inside <EDIT_PROPOSAL> and </EDIT_PROPOSAL> tags. If you are just answering a question, summarizing, or conversing, do NOT use these tags."

        if not raw_req.task or raw_req.task.strip() == "Process the attached context intelligently.":
            llm_prompt = abstracted_text + adaptive_instruction
        else:
            llm_prompt = f"User Instruction: {raw_req.task}\n\nContext:\n{abstracted_text}" + adaptive_instruction
        
        # 5. Model Abstraction Layer Execution
        actual_model = raw_req.model_pref if route_decision != "LOCAL" else "local_ollama"
        if route_decision == "BLOCK": actual_model = "NONE"
        yield format_event("model", f"Executing AI Model ({actual_model})...", "")
        
        generated_output = await self.llm_gateway.process(llm_prompt, route_decision, raw_req.model_pref)
        
        # 6. Reinjection
        yield format_event("reinject", "Reinjecting SRD mappings...", "")
        if route_decision != "BLOCK":
            final_output = ReinjectorService.reinject(generated_output, mapping)
        else:
            final_output = generated_output
            
        # 7. Judge Model Verification
        yield format_event("judge", "Verifying Safety with Judge...", "")
        judge_res = await self.judge.evaluate(raw_text, final_output)
        
        # Final Payload Event
        final_payload = {
            "step": "complete",
            "output": final_output,
            "risk_level": risk_level,
            "route": route_decision,
            "explanation": explanation,
            "judge": judge_res,
            "srd_count": srd_count,
            "input_hash": input_hash,
            "model_used": actual_model
        }
        yield f"data: {json.dumps(final_payload)}\n\n"
