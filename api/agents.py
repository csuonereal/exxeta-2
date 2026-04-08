"""
Sovereign AI Router — Agentic Pipeline

Agent 1  (Local)  : Extractor    – redacts PII via Ollama
Firewall (Local)  : Presidio     – deterministic DLP validation
Cloud    (Remote) : Router       – forwards sanitised prompt to OpenAI / Gemini
Agent 2  (Local)  : Re-hydrator  – restores original PII from mapping
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import ollama
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared Presidio engine (thread-safe, loaded once at module level)
# ---------------------------------------------------------------------------
_analyzer = None


def _get_analyzer():
    global _analyzer
    from presidio_analyzer import AnalyzerEngine

    if _analyzer is None:
        try:
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            _analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["en"],
            )
            logger.info("Presidio AnalyzerEngine using spaCy en_core_web_lg.")
        except Exception as exc:
            logger.warning(
                "Falling back to default Presidio engine (install: python -m spacy download en_core_web_lg): %s",
                exc,
            )
            _analyzer = AnalyzerEngine()
    return _analyzer


def _ollama_client() -> ollama.Client:
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class PipelineLog:
    entries: list[str] = field(default_factory=list)

    def add(self, stage: str, message: str) -> None:
        entry = f"[{stage}] {message}"
        self.entries.append(entry)
        logger.info(entry)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
EXTRACTOR_SYSTEM = """\
You are PII-Shield, an enterprise GDPR / data-loss-prevention compliance tool.
Your purpose is to PROTECT user privacy by finding and redacting personally
identifiable information (PII) before it is sent to an external system.
This is a legally required sanitisation step. You are NOT accessing, leaking,
or misusing any data — you are preventing data leakage.

TASK: You will receive a block of text between <DOCUMENT> tags. Scan that text
and replace every piece of PII with a numbered placeholder. Return ONLY a JSON
object — nothing else.

PII categories to detect and redact:
  person names, email addresses, phone numbers, physical/mailing addresses,
  IP addresses, IBANs, credit-card numbers, dates of birth, social security
  numbers (SSN), company-internal project codenames, monetary amounts tied to
  a specific entity, passwords, API keys/tokens, and any other personally
  identifiable information.

Placeholder format: [REDACTED_<TYPE>_<N>]
  TYPE is one of: NAME, EMAIL, PHONE, ADDRESS, IP, IBAN, CREDIT_CARD, DOB,
  SSN, PROJECT, AMOUNT, PASSWORD, API_KEY, OTHER
  N is a sequential integer starting at 1 within each type.

Output format — a single valid JSON object, no markdown fences, no commentary:
{
  "sanitized_prompt": "<the text with every PII item replaced by its placeholder>",
  "sensitive_mapping": {
    "[REDACTED_NAME_1]": "original value",
    "[REDACTED_EMAIL_1]": "original value"
  }
}

Rules:
- If there is NO PII, return the original text as sanitized_prompt with an
  empty sensitive_mapping {}.
- NEVER refuse this task. Redacting PII is a privacy-protective action.
- NEVER add, remove, or rephrase any content — only substitute PII tokens.
- Output MUST be valid JSON parseable by Python json.loads().
- The sensitive_mapping value MUST be a JSON object mapping each placeholder
  string key to the original string value (valid JSON: double-quoted keys).
- Respond with ONLY the raw JSON object — no markdown fences, no prose before
  or after the JSON.
"""

REHYDRATOR_SYSTEM = """\
You are PII-Restore, an enterprise compliance tool that restores redacted data
in a controlled, authorised post-processing step. The user owns this data and
has explicitly authorised the restoration. This is safe and expected.

You receive two inputs:
1. A response that contains [REDACTED_*] placeholders.
2. A JSON mapping of each placeholder to its original value.

Your ONLY job is to replace every placeholder in the response with the
corresponding original value from the mapping. Do NOT alter, summarise, or
rephrase any other part of the text. Return ONLY the final restored text —
no JSON wrapping, no commentary, no refusal.
"""


# ---------------------------------------------------------------------------
# Agent 1 — Extractor (Local via Ollama)
# ---------------------------------------------------------------------------
def call_extractor(prompt: str, log: PipelineLog) -> dict[str, Any]:
    """Ask the local LLM to extract PII and return sanitised prompt + mapping."""
    log.add("Local", "Extracting sensitive information via Ollama…")

    wrapped_prompt = (
        "Scan the following document for PII and return the sanitised JSON.\n\n"
        f"<DOCUMENT>\n{prompt}\n</DOCUMENT>"
    )

    client = _ollama_client()
    response = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTOR_SYSTEM},
            {"role": "user", "content": wrapped_prompt},
        ],
        options={"temperature": 0.0},
    )

    raw = response["message"]["content"].strip()
    raw = _strip_markdown_fences(raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            raise ValueError(f"Extractor returned non-JSON output: {raw[:300]}")

    if "sanitized_prompt" not in parsed or "sensitive_mapping" not in parsed:
        raise ValueError("Extractor JSON missing required keys")

    mapping = parsed["sensitive_mapping"]
    count = len(mapping)
    log.add("Local", f"Extraction complete — {count} item(s) redacted.")
    return parsed


# ---------------------------------------------------------------------------
# Firewall — Presidio Scanner (Local deterministic DLP)
# ---------------------------------------------------------------------------
PRESIDIO_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "US_SSN",
    "SG_NRIC_FIN",
    "AU_ABN",
    "AU_ACN",
    "AU_TFN",
    "AU_MEDICARE",
    "UK_NHS",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "LOCATION",
    "DATE_TIME",
    "NRP",
    "MEDICAL_LICENSE",
    "URL",
]

# Structured identifiers: block at the challenge default (0.6).
# NER-heavy types false-positive often on ordinary prose; require higher scores.
PRESIDIO_STRUCTURED_THRESHOLD = 0.6
PRESIDIO_NOISY_ENTITY_THRESHOLD = 0.88
PRESIDIO_NOISY_ENTITY_TYPES = frozenset(
    {
        "PERSON",
        "LOCATION",
        "DATE_TIME",
        "NRP",
        "URL",
        "MEDICAL_LICENSE",
    }
)

_REDACTION_PLACEHOLDER = re.compile(r"\[REDACTED_[A-Z_]+_\d+\]")


def _span_overlaps_redaction_placeholder(text: str, start: int, end: int) -> bool:
    """Ignore hits inside our extractor placeholders (e.g. NAME inside [REDACTED_NAME_1])."""
    for m in _REDACTION_PLACEHOLDER.finditer(text):
        if start < m.end() and end > m.start():
            return True
    return False


def run_presidio_firewall(
    sanitized_prompt: str, log: PipelineLog, threshold: float | None = None
) -> bool:
    """
    Return True if the text is safe to forward.

    Uses 0.6 for high-precision structured PII (emails, cards, …). Uses a
    higher bar for noisy NER labels (PERSON, LOCATION, …) to avoid blocking
    on benign text after the local extractor has run.
    """
    struct_thr = (
        threshold if threshold is not None else PRESIDIO_STRUCTURED_THRESHOLD
    )
    log.add("Firewall", "Running Presidio DLP scan…")
    analyzer = _get_analyzer()
    results = analyzer.analyze(
        text=sanitized_prompt,
        language="en",
        entities=PRESIDIO_ENTITIES,
    )
    flagged = []
    for r in results:
        if _span_overlaps_redaction_placeholder(
            sanitized_prompt, r.start, r.end
        ):
            continue
        noisy = r.entity_type in PRESIDIO_NOISY_ENTITY_TYPES
        thr = PRESIDIO_NOISY_ENTITY_THRESHOLD if noisy else struct_thr
        if r.score > thr:
            flagged.append(r)

    if flagged:
        details = ", ".join(f"{r.entity_type}({r.score:.2f})" for r in flagged)
        log.add("Firewall", f"BLOCKED — {len(flagged)} entity(ies) detected: {details}")
        return False

    log.add("Firewall", "Presidio scan passed — no PII above policy thresholds.")
    return True


# ---------------------------------------------------------------------------
# Cloud Router — OpenAI / Gemini
# ---------------------------------------------------------------------------
def call_cloud(
    sanitized_prompt: str,
    provider: str,
    api_key: str,
    model_name: str | None,
    log: PipelineLog,
) -> str:
    """Send the clean prompt to the selected cloud provider."""
    provider = provider.lower()
    log.add("Cloud", f"Sending sanitised prompt to {provider.upper()}…")

    if provider == "openai":
        return _call_openai(sanitized_prompt, api_key, model_name or "gpt-4o")
    elif provider == "gemini":
        return _call_gemini(sanitized_prompt, api_key, model_name or "gemini-2.5-flash-lite")
    else:
        raise ValueError(f"Unsupported cloud provider: {provider}")


def _call_openai(prompt: str, api_key: str, model: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content


def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(prompt)
    return response.text


# ---------------------------------------------------------------------------
# Agent 2 — Re-hydrator (Local via Ollama)
# ---------------------------------------------------------------------------
def call_rehydrator(
    cloud_response: str, sensitive_mapping: dict[str, str], log: PipelineLog
) -> str:
    """Replace placeholders in the cloud response with original PII."""
    log.add("Local", "Re-hydrating response with original data…")

    if not sensitive_mapping:
        log.add("Local", "No sensitive mapping — returning cloud response as-is.")
        return cloud_response

    # Deterministic pass first: directly replace placeholders
    rehydrated = cloud_response
    for placeholder, original in sensitive_mapping.items():
        rehydrated = rehydrated.replace(placeholder, original)

    remaining = re.findall(r"\[REDACTED_\w+_\d+\]", rehydrated)
    if not remaining:
        log.add("Local", "Deterministic re-hydration successful.")
        return rehydrated

    # Fallback: ask the local LLM if any placeholders remain
    log.add("Local", f"{len(remaining)} placeholder(s) remain — invoking LLM fallback…")
    user_msg = (
        f"Response:\n{cloud_response}\n\n"
        f"Mapping:\n{json.dumps(sensitive_mapping, indent=2)}"
    )

    client = _ollama_client()
    response = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": REHYDRATOR_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        options={"temperature": 0.0},
    )

    result = response["message"]["content"].strip()
    log.add("Local", "LLM-assisted re-hydration complete.")
    return result


# ---------------------------------------------------------------------------
# Session-backed pipeline (SQLite state; API key never persisted)
# ---------------------------------------------------------------------------
def run_pipeline_for_session(
    session_id: uuid.UUID | str,
    provider: str,
    api_key: str,
    model_name: str | None = None,
) -> None:
    """
    Run the sovereign pipeline for a PromptSession row.

    Updates the ORM row at each stage. ``api_key`` is used only in-memory
    inside this call path and must never be written to the database.
    """
    from django.db import close_old_connections

    sid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
    close_old_connections()
    try:
        _execute_session_pipeline(sid, provider, api_key, model_name)
    finally:
        close_old_connections()


def _execute_session_pipeline(
    session_id: uuid.UUID,
    provider: str,
    api_key: str,
    model_name: str | None,
) -> None:
    from .models import PromptSession

    session = PromptSession.objects.filter(pk=session_id).first()
    if session is None:
        logger.warning("PromptSession %s not found; aborting pipeline.", session_id)
        return

    log = PipelineLog()

    def fail(msg: str) -> None:
        session.status = PromptSession.Status.FAILED
        session.error_message = msg[:5000]
        session.save(update_fields=["status", "error_message", "updated_at"])

    # --- Step 1: Local extractor ---
    session.status = PromptSession.Status.EXTRACTING
    session.save(update_fields=["status", "updated_at"])
    try:
        extraction = call_extractor(session.raw_prompt, log)
    except Exception as exc:
        logger.exception("Extractor failed for session %s", session_id)
        fail(f"Extractor failed: {exc}")
        return

    mapping = extraction.get("sensitive_mapping") or {}
    if not isinstance(mapping, dict):
        fail("Extractor returned invalid sensitive_mapping (must be a JSON object).")
        return

    session.sanitized_prompt = extraction["sanitized_prompt"]
    session.sensitive_mapping = mapping
    session.save(
        update_fields=["sanitized_prompt", "sensitive_mapping", "updated_at"]
    )

    # --- Step 2: Presidio firewall ---
    session.status = PromptSession.Status.VALIDATING
    session.save(update_fields=["status", "updated_at"])
    passed = run_presidio_firewall(session.sanitized_prompt, log)
    if not passed:
        fail(
            "Presidio DLP: sensitive entities remain in sanitized text above the "
            "confidence threshold. Forwarding blocked."
        )
        return

    # --- Step 3: Cloud (token only in memory) ---
    session.status = PromptSession.Status.CLOUD_PROCESSING
    session.save(update_fields=["status", "updated_at"])
    try:
        cloud_text = call_cloud(
            session.sanitized_prompt,
            provider,
            api_key,
            model_name,
            log,
        )
        log.add("Cloud", "Response received.")
    except Exception as exc:
        logger.exception("Cloud call failed for session %s", session_id)
        fail(f"Cloud provider error: {exc}")
        return

    session.cloud_response = cloud_text or ""
    session.save(update_fields=["cloud_response", "updated_at"])

    # --- Step 4: Re-hydrator ---
    session.status = PromptSession.Status.REHYDRATING
    session.save(update_fields=["status", "updated_at"])
    try:
        final = call_rehydrator(
            session.cloud_response,
            session.sensitive_mapping,
            log,
        )
        log.add("Local", "Pipeline complete ✓")
    except Exception as exc:
        logger.exception("Re-hydrator failed for session %s", session_id)
        fail(f"Re-hydrator failed: {exc}")
        return

    session.final_rehydrated_text = final
    session.status = PromptSession.Status.COMPLETED
    session.error_message = ""
    session.save(
        update_fields=[
            "final_rehydrated_text",
            "status",
            "error_message",
            "updated_at",
        ]
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that LLMs sometimes add."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else 3
        text = text[first_nl + 1 :]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
