import uuid
import sqlite3
import hashlib
import hmac
import base64
import json
import os
import time
import secrets
from pathlib import Path
from typing import Any
from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import study_agent as agent

app = FastAPI(title="Study AI Agent API", version="1.0.0")

frontend_url = os.getenv("FRONTEND_URL", "").strip()
allowed_origins = [x.strip() for x in frontend_url.split(",") if x.strip()]
allowed_origins.extend([
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PENDING_QUIZZES: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

AUTH_DB = Path(__file__).resolve().parent / "studyai_users.db"
AUTH_TOKEN_TTL = 7 * 24 * 60 * 60
AUTH_SECRET = os.getenv("STUDYAI_AUTH_SECRET", "studyai-local-development-secret-change-me")


def init_auth_db():
    conn = sqlite3.connect(AUTH_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


init_auth_db()


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, hash_b64 = stored.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(hash_b64.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120_000,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_auth_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + AUTH_TOKEN_TTL,
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{body}.{sig}"


def get_user_from_token(token: str):
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            AUTH_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        provided = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        if not hmac.compare_digest(provided, expected):
            return None

        payload = json.loads(
            base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
        )
        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        user_id = int(payload["user_id"])
        conn = sqlite3.connect(AUTH_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def require_auth(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = authorization.split(" ", 1)[1].strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    CURRENT_USER.set(user)
    return user


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    name = req.name.strip()
    email = req.email.strip().lower()
    password = req.password

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    conn = sqlite3.connect(AUTH_DB)
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password)),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()

    return {
        "token": create_auth_token(int(user_id)),
        "user": {"id": int(user_id), "name": name, "email": email},
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()

    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name, email, password_hash, created_at FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()

    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "token": create_auth_token(int(row["id"])),
        "user": {
            "id": int(row["id"]),
            "name": row["name"],
            "email": row["email"],
            "created_at": row["created_at"],
        },
    }


@app.get("/api/auth/me", dependencies=[Depends(require_auth)])
def current_user(user=Depends(require_auth)):
    return {"user": user}


@app.post("/api/auth/logout", dependencies=[Depends(require_auth)])
def logout(user=Depends(require_auth)):
    # Tokens are stateless; the frontend removes the token on logout.
    return {"message": "Logged out successfully."}



class ChatMessage(BaseModel):
    role: str
    text: str


class AskRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class QuizRequest(BaseModel):
    topic: str
    count: int = 5


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[str]


class SmartNotesRequest(BaseModel):
    topic: str


class AgentActionRequest(BaseModel):
    action: str = "auto"
    topic: str = ""
    question: str = ""
    days: int = 1
    minutes_per_day: int = 60


# ============================================================
# PER-USER LEARNING MEMORY
# ============================================================
# Authentication identifies the student. Their learning profile is
# stored separately so quiz history, progress, questions, and study
# plans cannot leak between accounts.

USER_MEMORY_ROOT = Path(__file__).resolve().parent / "storage" / "users"
CURRENT_USER = ContextVar("studyai_current_user", default=None)

def _user_memory_path(user_id: int) -> Path:
    return USER_MEMORY_ROOT / str(int(user_id)) / "student_memory.json"

def _load_user_memory(user_id: int):
    path = _user_memory_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        return agent.default_memory()

    try:
        import json as _json
        with path.open("r", encoding="utf-8") as file:
            stored = _json.load(file)
        base = agent.default_memory()
        base["student"].update(stored.get("student", {}))
        base["topics"].update(stored.get("topics", {}))
        base["quiz_history"] = stored.get("quiz_history", [])
        base["question_history"] = stored.get("question_history", [])
        base["recommendations"] = stored.get("recommendations", [])
        base["study_plans"] = stored.get("study_plans", [])
        return base
    except (ValueError, OSError, TypeError):
        return agent.default_memory()

def _save_user_memory(memory_data, user=None):
    user = user or CURRENT_USER.get()
    if not user:
        raise RuntimeError("No authenticated user context is available.")

    path = _user_memory_path(int(user["id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        _json.dump(memory_data, file, indent=2)
    temp_path.replace(path)

# Route all study_agent persistence through the authenticated user's file.
# This also protects planner functions that call agent.save_memory() internally.
agent.load_memory = lambda: _load_user_memory(int(CURRENT_USER.get()["id"])) if CURRENT_USER.get() else agent.default_memory()
agent.save_memory = _save_user_memory

def memory(user=None):
    user = user or CURRENT_USER.get()
    if not user:
        raise RuntimeError("No authenticated user context is available.")
    return _load_user_memory(int(user["id"]))


def analytics_payload(user=None):
    """Build lightweight learning analytics from persisted quiz history."""
    m = memory(user)
    history = m.get("quiz_history", [])
    student = m.get("student", {})

    recent = history[-10:]
    recent_scores = [float(x.get("percentage", 0)) for x in recent]
    recent_average = round(sum(recent_scores) / len(recent_scores), 1) if recent_scores else 0.0

    if len(recent_scores) >= 2:
        previous_average = sum(recent_scores[:-1]) / len(recent_scores[:-1])
        change = round(recent_scores[-1] - previous_average, 1)
    else:
        change = 0.0

    streak = 0
    for item in reversed(history):
        if item.get("percentage") is None:
            break
        streak += 1

    return {
        "recent_quizzes": recent,
        "recent_average": recent_average,
        "latest_score": recent_scores[-1] if recent_scores else None,
        "change_vs_previous": change,
        "quiz_streak": streak,
        "total_quizzes": student.get("total_quizzes", 0),
        "total_questions": student.get("total_quiz_questions", 0),
        "total_correct": student.get("total_correct", 0),
    }


def dashboard_payload(user):
    m = memory(user)
    student = m.get("student", {})
    total_questions = student.get("total_questions", 0)
    quiz_questions = student.get("total_quiz_questions", 0)
    correct = student.get("total_correct", 0)

    quiz_accuracy = round((correct / quiz_questions) * 100, 1) if quiz_questions else 0.0

    topics = []
    for topic, data in m.get("topics", {}).items():
        accuracy = agent.get_topic_accuracy(data)
        topics.append({
            "topic": topic,
            "accuracy": round(accuracy, 1) if accuracy is not None else None,
            "attempts": data.get("attempts", 0),
            "questions": data.get("quiz_questions", 0),
            "correct": data.get("correct", 0),
            "last_activity": data.get("last_activity"),
        })

    weak = [
        x for x in topics
        if x["accuracy"] is not None and x["accuracy"] < 75
    ]
    strong = [
        x for x in topics
        if x["accuracy"] is not None and x["accuracy"] >= 75
    ]

    weak.sort(key=lambda x: x["accuracy"])
    strong.sort(key=lambda x: x["accuracy"], reverse=True)

    return {
        "student": {
            "total_questions": total_questions,
            "total_quizzes": student.get("total_quizzes", 0),
            "quiz_questions": quiz_questions,
            "correct": correct,
            "accuracy": quiz_accuracy,
        },
        "topics": topics,
        "weak_topics": weak[:5],
        "strong_topics": strong[:5],
        "recommendation": agent.generate_recommendation(m),
        "decision": agent.choose_next_action(m),
        "recent_quizzes": m.get("quiz_history", [])[-10:][::-1],
        "analytics": analytics_payload(),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Study AI Agent API"}


@app.get("/api/dashboard")
def dashboard(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    return dashboard_payload(user)


@app.get("/api/analytics")
def analytics(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    return analytics_payload(user)


@app.get("/api/memory", dependencies=[Depends(require_auth)])
def get_memory(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    return memory(user)


@app.get("/api/decision", dependencies=[Depends(require_auth)])
def decision(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    return agent.choose_next_action(memory(user))


@app.get("/api/recommendation", dependencies=[Depends(require_auth)])
def recommendation(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    return {"recommendation": agent.generate_recommendation(memory(user))}


@app.post("/api/agent/execute", dependencies=[Depends(require_auth)])
def execute_agent_action(req: AgentActionRequest, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    """Tool-calling gateway: the agent selects and executes one learning tool."""
    m = memory()
    requested = (req.action or "auto").strip().lower()
    question = (req.question or "").strip()
    topic = agent.normalize_topic(req.topic or "")

    if requested == "auto":
        if question:
            detected = agent.detect_intent(question)
            intent = detected if isinstance(detected, str) else str(detected.get("intent", "explain"))
            topic = topic or agent.normalize_topic(agent.extract_topic(question))
            mapping = {
                "quiz": "quiz",
                "study_plan": "plan",
                "summary": "summarize",
                "exam_answer": "exam",
                "explain": "explain",
            }
            requested = mapping.get(intent.lower(), "explain")
        else:
            requested = "next_action"

    tool = requested

    try:
        if tool == "next_action":
            result = agent.choose_next_action(m)
            return {"tool": tool, "status": "completed", "result": result}

        if tool == "analyze":
            analytics = analytics_payload()
            result = {
                "analytics": analytics,
                "weak_topics": agent.get_weak_topics(m, 5),
                "strong_topics": agent.get_strong_topics(m, 5),
                "recommendation": agent.generate_recommendation(m),
            }
            return {"tool": tool, "status": "completed", "result": result}

        if tool == "search":
            if not question:
                raise HTTPException(status_code=400, detail="Enter a question or search query.")
            database = agent.load_vector_database()
            results = agent.search_pdf(question, database)
            items = [{"page": r.get("page"), "score": round(float(r.get("score", 0)), 4), "text": r.get("text", "")} for r in results]
            return {"tool": tool, "status": "completed", "result": {"query": question, "results": items}}

        database = agent.load_vector_database()
        if not topic and question:
            topic = agent.normalize_topic(agent.extract_topic(question))
        topic = topic or "General"
        results = agent.search_pdf(topic, database)
        context = agent.build_context(results)

        if tool == "explain":
            result = agent.explain_topic(topic, context)
        elif tool == "summarize":
            result = agent.summarize_topic(topic, context)
        elif tool == "exam":
            result = agent.generate_exam_answer(question or f"Explain {topic}", 8, context)
        elif tool == "quiz":
            count = 5
            difficulty = agent.choose_quiz_difficulty(m, topic)
            questions = agent.generate_quiz_questions(topic, context, difficulty=difficulty, count=count)
            safe = [{"question": q.get("question", ""), "options": q.get("options", {}), "topic": q.get("topic", topic)} for q in questions]
            result = {"topic": topic, "difficulty": difficulty, "questions": safe}
        elif tool == "plan":
            result = agent.create_adaptive_study_plan(m, days=max(1, min(req.days, 30)), minutes_per_day=max(15, min(req.minutes_per_day, 480)))
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent tool: {tool}")

        return {"tool": tool, "status": "completed", "topic": topic, "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent tool '{tool}' failed: {exc}")


@app.post("/api/smart-notes", dependencies=[Depends(require_auth)])
def smart_notes(req: SmartNotesRequest, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    topic = req.topic.strip()

    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    topic = agent.normalize_topic(topic) or req.topic.strip()

    try:
        database = agent.load_vector_database()
        search_results = agent.search_pdf(topic, database)
        context = agent.build_context(search_results)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load study material: {exc}",
        )

    if not context:
        return {
            "topic": topic,
            "notes": "No matching study material was found for this topic.",
            "sources_available": False,
            "source_pages": [],
        }

    prompt = f"""You are StudyAI Smart Notes.

Create clear, structured study notes for the topic: {topic}

Use ONLY the study material provided below as the source.
Do not invent information that is not present in the study material.

Study material:
{context}

Create the notes using this structure:

# {topic}

## 1. Definition
Explain the concept simply.

## 2. Key Concepts
List the most important points.

## 3. Important Details
Explain important facts, rules, or mechanisms.

## 4. Example
Give a simple example if supported by the material.

## 5. Exam Points
List important points a student should remember.

## 6. Quick Revision
Give a short revision summary.
"""

    try:
        notes = agent.ask_ollama(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not generate smart notes: {exc}",
        )

    source_pages = sorted({item.get("page") for item in search_results if item.get("page") is not None})[:6]

    return {
        "topic": topic,
        "notes": notes,
        "sources_available": True,
        "source_pages": source_pages,
    }


@app.post("/api/ask", dependencies=[Depends(require_auth)])
def ask(req: AskRequest, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    m = memory()
    topic = agent.extract_topic(question)
    topic = agent.normalize_topic(topic) or "General"

    try:
        database = agent.load_vector_database()
        search_results = agent.search_pdf(question, database)
        context = agent.build_context(search_results)
    except Exception:
        search_results = []
        context = ""

    recent_history = []
    for item in req.history[-8:]:
        role = "Student" if item.role.lower() == "user" else "StudyAI"
        recent_history.append(f"{role}: {item.text.strip()}")
    conversation = "\n".join(recent_history) or "(No previous conversation.)"

    answer = agent.ask_ollama(
        f"""You are StudyAI, a patient personal tutor.

Use the study material below as the primary source. Do not invent facts that
are not supported by the material. Use the conversation history only to
understand references and follow-up questions.

Conversation history:
{conversation}

Current student question:
{question}

Study material:
{context}

Answer in a clear, student-friendly way. If useful, use short headings,
bullet points, examples, or an exam-ready explanation. If the material does
not contain enough information, say that clearly instead of making it up."""
    )

    agent.record_question(m, question, topic)
    agent.save_memory(m)

    source_pages = sorted({item["page"] for item in search_results})[:6] if search_results else []

    return {
        "question": question,
        "topic": topic,
        "answer": answer,
        "sources_available": bool(context),
        "source_pages": source_pages[:6],
    }


@app.post("/api/quiz", dependencies=[Depends(require_auth)])
def create_quiz(req: QuizRequest, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    topic = agent.normalize_topic(req.topic) or "General"
    count = max(1, min(req.count, 10))
    m = memory()

    try:
        database = agent.load_vector_database()
        search_results = agent.search_pdf(topic, database)
        context = agent.build_context(search_results)
    except Exception:
        context = ""

    difficulty = agent.choose_quiz_difficulty(m, topic)
    questions = agent.generate_quiz_questions(
        topic, context, difficulty=difficulty, count=count
    )

    if not questions:
        raise HTTPException(status_code=500, detail="Could not generate quiz.")

    quiz_id = str(uuid.uuid4())
    PENDING_QUIZZES[quiz_id] = {
        "user_id": int(CURRENT_USER.get()["id"]),
        "topic": topic,
        "difficulty": difficulty,
        "questions": questions,
    }

    safe_questions = []
    for q in questions:
        safe_questions.append({
            "question": q.get("question", ""),
            "options": q.get("options", {}),
            "topic": q.get("topic", topic),
            "explanation": q.get("explanation", ""),
        })

    return {
        "quiz_id": quiz_id,
        "topic": topic,
        "difficulty": difficulty,
        "questions": safe_questions,
    }


@app.post("/api/quiz/submit", dependencies=[Depends(require_auth)])
def submit_quiz(req: QuizSubmitRequest, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    quiz = PENDING_QUIZZES.get(req.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or already submitted.")

    if int(quiz.get("user_id", -1)) != int(CURRENT_USER.get()["id"]):
        raise HTTPException(status_code=403, detail="This quiz belongs to another account.")

    PENDING_QUIZZES.pop(req.quiz_id, None)

    questions = quiz["questions"]
    if len(req.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Answer count does not match quiz.")

    score = 0
    wrong_topics = []
    question_results = []

    def normalize_answer(value, options=None):
        """Convert A/B/C/D or an option label/text into a stable answer key."""
        if value is None:
            return ""

        text = str(value).strip()
        if not text:
            return ""

        upper = text.upper()

        # Direct answer key: A, B, C or D
        if upper in {"A", "B", "C", "D"}:
            return upper

        # Answer returned as 'A) ...', 'B. ...', etc.
        import re
        match = re.match(r"^([A-D])\s*[\)\.\:\-]", upper)
        if match:
            return match.group(1)

        # If the backend stored the full option text, map it back to A-D.
        if isinstance(options, dict):
            items = list(options.items())
        elif isinstance(options, list):
            items = list(zip(["A", "B", "C", "D"], options))
        else:
            items = []

        cleaned = re.sub(r"^[A-Da-d]\s*[\)\.\:\-]\s*", "", text).strip().casefold()
        for key, option in items:
            option_text = re.sub(
                r"^[A-Da-d]\s*[\)\.\:\-]\s*",
                "",
                str(option).strip(),
            ).strip().casefold()
            if cleaned == option_text:
                return str(key).strip().upper()

        return upper

    for q, answer in zip(questions, req.answers):
        selected = normalize_answer(answer, q.get("options"))
        correct = normalize_answer(q.get("answer"), q.get("options"))

        is_correct = selected == correct and correct in {"A", "B", "C", "D"}

        if is_correct:
            score += 1
        else:
            wrong_topics.append(q.get("topic", quiz["topic"]))

        options = q.get("options", {})
        if isinstance(options, list):
            options = dict(zip(["A", "B", "C", "D"], options))

        selected_text = options.get(selected, "") if isinstance(options, dict) else ""
        correct_text = options.get(correct, "") if isinstance(options, dict) else ""

        question_results.append({
            "question": q.get("question", ""),
            "selected_answer": selected,
            "selected_text": selected_text,
            "correct_answer": correct,
            "correct_text": correct_text,
            "is_correct": is_correct,
            "topic": q.get("topic", quiz["topic"]),
            "explanation": q.get("explanation", ""),
        })

    m = memory()
    agent.record_quiz(
        m,
        quiz["topic"],
        score,
        len(questions),
        wrong_topics,
    )
    agent.save_memory(m)

    total = len(questions)
    percentage = round((score / total) * 100, 1) if total else 0

    return {
        "topic": quiz["topic"],
        "difficulty": quiz["difficulty"],
        "score": score,
        "total": total,
        "percentage": percentage,
        "wrong_topics": wrong_topics,
        "question_results": question_results,
        "recommendation": agent.generate_recommendation(m),
        "next_decision": agent.choose_next_action(m),
    }


@app.get("/api/study-plan", dependencies=[Depends(require_auth)])
def study_plan(days: int = 1, minutes_per_day: int = 60, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    """Return a deterministic adaptive study plan based on current performance."""
    m = memory()
    days = max(1, min(days, 30))
    minutes_per_day = max(15, min(minutes_per_day, 480))

    try:
        plan = agent.create_adaptive_study_plan(
            m,
            days=days,
            minutes_per_day=minutes_per_day,
        )
        return plan
    except AttributeError:
        raise HTTPException(
            status_code=500,
            detail="Adaptive Study Planner is not available in study_agent.py.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create study plan: {exc}")


@app.post("/api/study-plan", dependencies=[Depends(require_auth)])
def refresh_study_plan(days: int = 1, minutes_per_day: int = 60, user=Depends(require_auth)):
    CURRENT_USER.set(user)
    """Create and persist a fresh adaptive study plan."""
    return study_plan(days=days, minutes_per_day=minutes_per_day, user=user)


@app.post("/api/study-session", dependencies=[Depends(require_auth)])
def start_study_session(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    """
    Start the first actionable task from today's adaptive study plan.

    Learning/review tasks return tutor content.
    Practice/assessment tasks return a quiz ready for submission.
    """
    m = memory()

    try:
        plan = agent.create_adaptive_study_plan(
            m,
            days=1,
            minutes_per_day=60,
        )
    except AttributeError:
        raise HTTPException(
            status_code=500,
            detail="Adaptive Study Planner is not available in study_agent.py.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create today's study session: {exc}",
        )

    day = (plan.get("days_plan") or [{}])[0]
    tasks = day.get("tasks") or []

    if not tasks:
        raise HTTPException(status_code=500, detail="Today's plan has no tasks.")

    task = tasks[0]
    task_type = str(task.get("type", "review")).lower()
    topic = agent.normalize_topic(
        str(task.get("topic") or plan.get("priority_topic") or "General")
    ) or "General"

    # Review / learning tasks: retrieve material and teach immediately.
    if task_type in {"review", "learn", "discover", "advanced"}:
        review = ""
        try:
            database = agent.load_vector_database()
            context = agent.search_pdf(topic, database)
            if context:
                if task_type == "review":
                    review = agent.explain_topic(topic, context)
                else:
                    review = agent.answer_question(
                        f"Teach me {topic} for today's study session. "
                        "Focus on the most important concepts, examples, and exam points.",
                        context,
                    )
            else:
                review = f"No matching material was found for {topic} in the study PDF."
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not start the learning task: {exc}",
            )

        return {
            "status": "started",
            "mode": "learning",
            "task": task,
            "plan": plan,
            "topic": topic,
            "content": review,
            "message": f"Today's first task has started: {task.get('description', 'Study this topic.')}",
        }

    # Practice / assessment tasks: generate a quiz and return it to the UI.
    if task_type in {"practice", "assess"}:
        try:
            database = agent.load_vector_database()
            context = agent.search_pdf(topic, database)
        except Exception:
            context = ""

        difficulty = agent.choose_quiz_difficulty(m, topic)
        questions = agent.generate_quiz_questions(
            topic,
            context,
            difficulty=difficulty,
            count=5,
        )

        if not questions:
            raise HTTPException(
                status_code=500,
                detail="Could not generate the study-session quiz.",
            )

        quiz_id = str(uuid.uuid4())
        PENDING_QUIZZES[quiz_id] = {
            "user_id": int(CURRENT_USER.get()["id"]),
            "topic": topic,
            "difficulty": difficulty,
            "questions": questions,
        }

        safe_questions = [
            {
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                "topic": q.get("topic", topic),
                "explanation": q.get("explanation", ""),
            }
            for q in questions
        ]

        return {
            "status": "started",
            "mode": "quiz",
            "task": task,
            "plan": plan,
            "topic": topic,
            "quiz_id": quiz_id,
            "difficulty": difficulty,
            "questions": safe_questions,
            "message": f"Today's {task_type} task has started.",
        }

    return {
        "status": "started",
        "mode": "task",
        "task": task,
        "plan": plan,
        "topic": topic,
        "message": "Today's study task has started.",
    }


@app.post("/api/autonomous-session", dependencies=[Depends(require_auth)])
def autonomous_session(user=Depends(require_auth)):
    CURRENT_USER.set(user)
    m = memory()
    decision = agent.choose_next_action(m)
    topic = decision["topic"]

    context = ""
    review = ""
    if topic != "general":
        try:
            database = agent.load_vector_database()
            context = agent.search_pdf(topic, database)
            if context:
                review = agent.explain_topic(topic, context)
        except Exception as exc:
            review = f"Could not load review material: {exc}"

    return {
        "decision": decision,
        "topic": topic,
        "review": review,
        "message": (
            "The agent analyzed your memory and selected the next learning action. "
            "Start the adaptive quiz below to continue the loop."
        ),
    }
