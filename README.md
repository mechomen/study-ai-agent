# Study AI Agent — Student Dashboard Upgrade

This package adds a React/Vite web dashboard to the latest working Study AI Agent.

Architecture:
  React Dashboard -> FastAPI -> Study Agent -> Ollama + RAG -> student_memory.json

## 1. Backend

Open a terminal in `backend`:

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn api_server:app --reload --port 8000

Keep Ollama running.

IMPORTANT:
Copy your existing working `data` folder (containing `study.pdf`) and, if needed,
your `storage/vectors.json` into `backend/` so paths are:
    backend/data/study.pdf
    backend/storage/vectors.json

## 2. Frontend

Open another terminal in `frontend`:

    npm install
    npm run dev

Then open the URL printed by Vite, normally:
    http://localhost:5173

## Dashboard features

- Overall accuracy
- Quizzes completed
- Questions answered
- Strong topics
- Weak topics
- AI recommendation
- Agent decision engine
- Ask StudyAI
- Adaptive 5-question quizzes
- Quiz scoring and persistent memory updates
- Start Autonomous Session
- Adaptive review before practice

This is an MVP dashboard designed to keep the existing agent logic intact while
making the project easier to demonstrate.
