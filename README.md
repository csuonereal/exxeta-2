# 🛡️ Compliance-Aware AI Orchestration Middleware

An intelligent, API-driven middleware layer designed to abstract regulatory complexity and ensure the safe, compliant use of AI models across varied organizational workflows. 

The system acts as a secure buffer between user inputs (emails, documents, prompts) and Generative AI models. It natively anonymizes Sensitive Regulated Data (SRD), enforces deterministic risk-based routing policies, and validates results using an independent local "Judge" model to prevent compliance violations under frameworks like the GDPR and EU AI Act.

---

## ✨ System Highlights
- **Multi-Modal Parsing:** Handles basic text and structured emails natively.
- **Zero-Persistance SRD Detection:** Identifies sensitive elements natively and replaces them transiently using placeholders (`<PERSON_1>`). Raw SRD is never persisted to databases.
- **Dynamic Routing Engine:** Automates routing to Proprietary Remote APIs when data is fully anonymized ("Minimal Risk"), but enforces hard fallback to complete **Local-Only Processing** if massive amounts of SRD are detected ("High Risk").
- **Multi-Model Abstraction Layer:** Interacts reliably with:
  - Local GPU Models (via **Ollama**)
  - Proprietary AI APIs (**OpenAI GPT-4o**, **Anthropic Claude**, **Google Gemini**)
- **Judge Verification Protocol:** A dedicated local model evaluates every generated output string for accidental SRD leakage or hallucination *before* returning it to the user.
- **Real-Time Visual Demo UI:** A sleek, fully interactive frontend dashboard available at the root URL to visualize the step-by-step pipeline behaviors.

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running locally.

### 1. Model Configuration
By default, the privacy layer and judge rely on local Ollama models. You must pull an LLM (e.g., `llama3` or `phi3`) before running:
```bash
ollama run llama3
```

### 2. Environment Variables
Create a `.env` file at the root of the project to define your routing behavior. 

```env
# Add one or more remote APIs to enable HYBRID routing
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="AI..."

# Change these to match your downloaded Ollama models
OLLAMA_SRD_MODEL=llama3
OLLAMA_JUDGE_MODEL=llama3
OLLAMA_ROUTING_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
```

### 3. Running Locally (Python Venv)
```bash
# Create and activate environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Dependencies
pip install -r requirements.txt

# Start the Application
uvicorn app.main:app --reload
```

### 4. Running via Docker
A `docker-compose.yml` is provided for containerized web hosting that communicates securely to your host machine's Ollama runner to maintain GPU acceleration.
```bash
docker-compose up --build
```

---

## 🚦 Endpoints & Usage

Once running, you can access the interactive UI and the API Documentation:
- **Interactive UI Dashboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **API Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Primary API
`POST /process`
```json
{
  "input_type": "text",
  "content": "Summarize my meeting with John Doe regarding SSN ***...",
  "task": "Extract action items",
  "model_pref": "auto" # can be 'local', 'openai', 'gemini'
}
```

---

## 🛠️ Tech Stack
- **FastAPI / Python 3.11** (Async API Services)
- **SQLAlchemy & SQLite** (Immutable Audit Logging)
- **Vanilla HTML/CSS/JS** (Projector-optimized UI Dashboard)
- **Docker** (Containerization)
