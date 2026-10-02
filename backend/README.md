# Study AI Agent Dashboard Backend

This folder contains the latest working Study AI Agent plus a FastAPI layer.

## Setup
1. Put your existing `data/study.pdf` and `storage/vectors.json` beside the backend
   or copy the `data` and `storage` folders from your working agent project.
2. Make sure Ollama is running and the models used by `study_agent.py` are available.
3. Create/activate a virtual environment.
4. Install: `pip install -r requirements.txt`
5. Start API: `uvicorn api_server:app --reload --port 8000`

API: http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs
