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
Match mapping keys case-insensitively for the TYPE part (e.g. [REDACTED_address_1]
equals [REDACTED_ADDRESS_1]). Replace every [REDACTED_*] token; none may remain.
"""

# Cloud must not materialize secrets; rehydration happens only on the client.
CLOUD_PLACEHOLDER_INSTRUCTION = """You are completing a privacy-controlled task.

SECRET TOKENS (only these carry real user data):
The user's text includes [REDACTED_NAME_1], [REDACTED_ADDRESS_1], [REDACTED_PHONE_1],
[REDACTED_IP_1], [REDACTED_SSN_1], etc. Copy each EXACTLY (same brackets, TYPE, number)
everywhere that specific secret is meant to appear (e.g. salutation, address block, body).

NEVER spell out those secrets as plain text—only the [REDACTED_*] tokens.

NORMAL LETTER LAYOUT (avoid fake "template tags"):
- Write a realistic business letter: real headings like **Date:**, **To:**, **Subject:**,
  and **Sincerely,** — not bracket labels such as [Letterhead], [Date], or [Company Name].
- For the date line, use "Date: _______________" or leave a blank line; do not invent a calendar date.
- For closing/signature, use lines such as "________________________" and
  "Authorized representative" / "Human Resources" — do not invent signer names.

GENERIC REFERENCES (no invented identities):
- For any role that has NO [REDACTED_*] token in the user message, never invent personal names
  (no "Sandra Weber", "John Doe", etc.). Write neutrally: "your direct supervisor",
  "Human Resources", "the reporting manager", "the undersigned".
- Do not invent company names; say "the company" or "your employer" if needed.

Temperature is set to 0: follow literally and deterministically."""

CLOUD_RETRY_USER_MESSAGE = (
    "Your previous answer was REJECTED: it contained raw secret values or invented names. "
    "Rewrite the COMPLETE letter from scratch. "
    "All sensitive facts from the original task must appear ONLY as the exact [REDACTED_*] "
    "tokens from the user message—never as spelled-out names, IDs, addresses, or IPs. "
    "Use a normal letter format (Date / To / Subject / Sincerely) with underscores for blanks—"
    "not [Letterhead]-style bracket tags. No fictional people: use 'your direct supervisor', "
    "'Human Resources', or similar neutral wording."
)

# Substrings this short are skipped to avoid false positives (e.g. "USA", "HR").
MIN_SENSITIVE_LEAK_LEN = 5

# TYPE may be NAME, ADDRESS, CREDIT_CARD, etc. (letters and underscores only before _N)
_PLACEHOLDER_IN_TEXT = re.compile(
    r"\[REDACTED_((?:[A-Za-z]+(?:_[A-Za-z]+)*)?)_(\d+)\]",
    re.IGNORECASE,
)


def _canonical_placeholder_key(type_part: str, index: str) -> str:
    return f"[REDACTED_{type_part.upper()}_{index}]"


def _mapping_by_canonical(sensitive_mapping: dict[str, Any]) -> dict[str, str]:
    """Exact keys plus canonical [REDACTED_TYPE_N] -> value for case-insensitive lookup."""
    by: dict[str, str] = {}
    for k, v in sensitive_mapping.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        k_st = k.strip()
        by[k_st] = v
        m = _PLACEHOLDER_IN_TEXT.fullmatch(k_st)
        if m:
            ck = _canonical_placeholder_key(m.group(1), m.group(2))
            by[ck] = v
    return by


def _decode_unicode_escapes(s: str) -> str:
    """Turn literal \\u00fc sequences into characters (some APIs return these)."""

    def u16(m: re.Match[str]) -> str:
        try:
            return chr(int(m.group(1), 16))
        except ValueError:
            return m.group(0)

    def u32(m: re.Match[str]) -> str:
        try:
            cp = int(m.group(1), 16)
            return chr(cp) if cp <= 0x10FFFF else m.group(0)
        except ValueError:
            return m.group(0)

    t = re.sub(r"\\u([0-9a-fA-F]{4})", u16, s)
    return re.sub(r"\\U([0-9a-fA-F]{8})", u32, t)


def _substitute_placeholders(text: str, lookup: dict[str, str]) -> str:
    """Replace [REDACTED_TYPE_N] using canonical TYPE (case-insensitive)."""

    def repl(m: re.Match[str]) -> str:
        ck = _canonical_placeholder_key(m.group(1), m.group(2))
        raw = m.group(0)
        return lookup.get(ck, lookup.get(raw, raw))

    return _PLACEHOLDER_IN_TEXT.sub(repl, text)


def _normalize_ws(s: str) -> str:
    return " ".join(s.split())


def _cloud_leaks_sensitive_values(
    cloud_text: str, sensitive_mapping: dict[str, Any]
) -> bool:
    """True if the model echoed a mapped secret (substring match, case-insensitive)."""
    if not cloud_text or not sensitive_mapping:
        return False
    hay = _normalize_ws(_decode_unicode_escapes(cloud_text)).casefold()
    for v in sensitive_mapping.values():
        if not isinstance(v, str):
            continue
        piece = _normalize_ws(_decode_unicode_escapes(v.strip())).casefold()
        if len(piece) < MIN_SENSITIVE_LEAK_LEN:
            continue
        if piece in hay:
            return True
    return False


def _force_mapped_secrets_to_placeholders(
    cloud_text: str, sensitive_mapping: dict[str, Any]
) -> str:
    """
    Replace any literal occurrence of mapped secret values with canonical [REDACTED_*] keys.

    Cloud models often echo PII despite instructions; this runs locally before storage so
    re-hydration always sees tokens, not raw secrets. Longest values first to avoid
    partial replacements. Matching is case-insensitive.
    """
    if not cloud_text or not sensitive_mapping:
        return cloud_text
    out = _decode_unicode_escapes(cloud_text)
    pairs: list[tuple[str, str]] = []
    for ph, val in sensitive_mapping.items():
        if not isinstance(ph, str) or not isinstance(val, str):
            continue
        v = val.strip()
        if len(v) < MIN_SENSITIVE_LEAK_LEN:
            continue
        m = _PLACEHOLDER_IN_TEXT.fullmatch(ph.strip())
        ck = (
            _canonical_placeholder_key(m.group(1), m.group(2))
            if m
            else ph.strip()
        )
        pairs.append((ck, v))
    pairs.sort(key=lambda x: len(x[1]), reverse=True)
    for ck, val in pairs:
        try:
            rx = re.compile(re.escape(val), re.IGNORECASE)
        except re.error:
            continue
        out = rx.sub(ck, out)
    return out


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
    sensitive_mapping: dict[str, Any] | None = None,
) -> str:
    """
    Send the sanitised prompt to the cloud provider.

    If ``sensitive_mapping`` is provided, detects when the model echoes raw mapped
    secrets and performs one strict retry; still leaking raises ValueError.
    """
    provider = provider.lower()
    log.add("Cloud", f"Sending sanitised prompt to {provider.upper()}…")

    if provider == "openai":
        model = model_name or "gpt-4o"
        text = _call_openai_first(sanitized_prompt, api_key, model)
    elif provider == "gemini":
        model = model_name or "gemini-2.5-flash-lite"
        text = _call_gemini_first(sanitized_prompt, api_key, model)
    else:
        raise ValueError(f"Unsupported cloud provider: {provider}")

    text = (text or "").strip()
    if sensitive_mapping and _cloud_leaks_sensitive_values(text, sensitive_mapping):
        log.add(
            "Cloud",
            "Model echoed mapped secrets — retrying once, then local token enforcement…",
        )
        if provider == "openai":
            text = _call_openai_retry(sanitized_prompt, api_key, model, text)
        else:
            text = _call_gemini_retry(sanitized_prompt, api_key, model, text)
        text = (text or "").strip()

    if sensitive_mapping:
        scrubbed = _force_mapped_secrets_to_placeholders(text, sensitive_mapping)
        if scrubbed != text:
            log.add(
                "Cloud",
                "Local enforcement: replaced echoed secrets with [REDACTED_*] tokens.",
            )
        text = scrubbed

    if sensitive_mapping and _cloud_leaks_sensitive_values(text, sensitive_mapping):
        raise ValueError(
            "Some sensitive values could not be aligned to [REDACTED_*] tokens "
            "(e.g. reformatted phone/IP). Try again or shorten the prompt."
        )

    return text


def _call_openai_first(prompt: str, api_key: str, model: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": CLOUD_PLACEHOLDER_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
    )
    return completion.choices[0].message.content or ""


def _call_openai_retry(
    prompt: str, api_key: str, model: str, bad_reply: str
) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": CLOUD_PLACEHOLDER_INSTRUCTION},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": bad_reply},
            {"role": "user", "content": CLOUD_RETRY_USER_MESSAGE},
        ],
    )
    return completion.choices[0].message.content or ""


def _call_gemini_generate(full_prompt: str, api_key: str, model: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(
        full_prompt,
        generation_config={"temperature": 0},
    )
    return (response.text or "").strip()


def _call_gemini_first(prompt: str, api_key: str, model: str) -> str:
    full = f"{CLOUD_PLACEHOLDER_INSTRUCTION}\n\n---\n\n{prompt}"
    return _call_gemini_generate(full, api_key, model)


def _call_gemini_retry(
    prompt: str, api_key: str, model: str, bad_reply: str
) -> str:
    full = (
        f"{CLOUD_PLACEHOLDER_INSTRUCTION}\n\n---\n\n{prompt}\n\n"
        f"---\nYOUR PREVIOUS DRAFT (INVALID — contained raw secrets):\n{bad_reply}\n\n"
        f"{CLOUD_RETRY_USER_MESSAGE}"
    )
    return _call_gemini_generate(full, api_key, model)


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

    lookup = _mapping_by_canonical(sensitive_mapping)
    text = _decode_unicode_escapes(cloud_response)
    rehydrated = _substitute_placeholders(text, lookup)

    if not _PLACEHOLDER_IN_TEXT.search(rehydrated):
        log.add("Local", "Deterministic re-hydration successful.")
        return rehydrated

    n_remain = len(_PLACEHOLDER_IN_TEXT.findall(rehydrated))
    log.add("Local", f"{n_remain} placeholder(s) remain — invoking LLM fallback…")
    user_msg = (
        f"Response:\n{rehydrated}\n\n"
        f"Mapping (JSON, UTF-8):\n"
        f"{json.dumps(sensitive_mapping, ensure_ascii=False, indent=2)}\n\n"
        "Replace every [REDACTED_..._N] token using the mapping. "
        "Keys match case-insensitively on the middle TYPE word. "
        "Output the complete restored text only — no placeholders left."
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

    result = _decode_unicode_escapes(response["message"]["content"].strip())
    result = _substitute_placeholders(result, lookup)

    if _PLACEHOLDER_IN_TEXT.search(result):
        log.add(
            "Local",
            "Some placeholders could not be mapped — check cloud output vs extractor keys.",
        )
    else:
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
            sensitive_mapping=session.sensitive_mapping,
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
