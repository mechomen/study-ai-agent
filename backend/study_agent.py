import os
import json
import re
from datetime import datetime
try:
    import ollama
except ImportError:
    ollama = None

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

import numpy as np
from pypdf import PdfReader


# ============================================================
# CONFIGURATION
# ============================================================

# Provider configuration
# Local: AI_PROVIDER=ollama, EMBED_PROVIDER=ollama
# Cloud: AI_PROVIDER=groq, EMBED_PROVIDER=sentence_transformers
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip().lower()
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama").strip().lower()

CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
ST_EMBED_MODEL = os.getenv("ST_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

PDF_FILE = os.getenv("PDF_FILE", "data/study.pdf")
VECTOR_FILE_OLLAMA = os.getenv("VECTOR_FILE_OLLAMA", "storage/vectors.json")
VECTOR_FILE_ST = os.getenv("VECTOR_FILE_ST", "storage/vectors_sentence_transformer.json")
MEMORY_FILE = "storage/student_memory.json"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 4

_embedding_model = None
_groq_client = None

def _vector_file():
    return VECTOR_FILE_ST if EMBED_PROVIDER in {"sentence_transformers", "sentence-transformer", "local"} else VECTOR_FILE_OLLAMA

def _get_sentence_transformer():
    global _embedding_model
    if _embedding_model is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed.")
        _embedding_model = SentenceTransformer(ST_EMBED_MODEL)
    return _embedding_model

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        if Groq is None:
            raise RuntimeError("groq is not installed.")
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing.")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


# ============================================================
# PDF LOADING
# ============================================================

def load_pdf():
    reader = PdfReader(PDF_FILE)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if text:
            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


# ============================================================
# CREATE CHUNKS
# ============================================================

def create_chunks(pages):
    chunks = []

    for page in pages:
        text = page["text"]
        start = 0

        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end].strip()

            if chunk:
                chunks.append({
                    "page": page["page"],
                    "text": chunk
                })

            start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# ============================================================
# CREATE EMBEDDING
# ============================================================

def create_embedding(text):
    """Create embeddings using the configured local/cloud provider."""
    if EMBED_PROVIDER in {"sentence_transformers", "sentence-transformer", "local"}:
        model = _get_sentence_transformer()
        embedding = model.encode(text, normalize_embeddings=False, convert_to_numpy=True)
        return embedding.tolist()

    if ollama is None:
        raise RuntimeError("Ollama is not installed. Set EMBED_PROVIDER=sentence_transformers.")

    response = ollama.embed(model=EMBED_MODEL, input=text)
    return response["embeddings"][0]


# ============================================================
# VECTOR DATABASE
# ============================================================

def build_vector_database(chunks):
    print("\nCreating embeddings...")

    database = []

    for i, chunk in enumerate(chunks):
        print(
            f"Embedding {i + 1}/{len(chunks)}",
            end="\r"
        )

        embedding = create_embedding(chunk["text"])

        database.append({
            "page": chunk["page"],
            "text": chunk["text"],
            "embedding": embedding
        })

    print("\nEmbeddings created.")

    os.makedirs("storage", exist_ok=True)

    with open(_vector_file(), "w", encoding="utf-8") as file:
        json.dump(database, file)

    print("Vector database saved.")


def load_vector_database():
    with open(_vector_file(), "r", encoding="utf-8") as file:
        return json.load(file)


def ensure_vector_database():
    """Build the provider-specific vector database when it does not exist."""
    if os.path.exists(_vector_file()):
        return load_vector_database()
    if not os.path.exists(PDF_FILE):
        raise FileNotFoundError(f"Study PDF not found: {PDF_FILE}")
    pages = load_pdf()
    chunks = create_chunks(pages)
    build_vector_database(chunks)
    return load_vector_database()


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)

    denominator = (
        np.linalg.norm(a) *
        np.linalg.norm(b)
    )

    if denominator == 0:
        return 0

    return np.dot(a, b) / denominator


# ============================================================
# SEARCH PDF
# ============================================================

def search_pdf(question, database):
    question_embedding = create_embedding(question)
    results = []

    for item in database:
        score = cosine_similarity(
            question_embedding,
            item["embedding"]
        )

        results.append({
            "score": float(score),
            "page": item["page"],
            "text": item["text"]
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:TOP_K]


# ============================================================
# BUILD CONTEXT
# ============================================================

def build_context(results):
    context = ""

    for result in results:
        context += (
            f"\n[Page {result['page']}]\n"
            f"{result['text']}\n"
        )

    return context


# ============================================================
# OLLAMA
# ============================================================

def ask_ollama(prompt, num_predict=512, temperature=0.3):
    """Backward-compatible wrapper for Ollama locally or Groq in cloud."""
    if AI_PROVIDER == "groq":
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=num_predict,
        )
        return response.choices[0].message.content or ""

    if ollama is None:
        raise RuntimeError("Ollama is not installed. Set AI_PROVIDER=groq for cloud deployment.")

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature, "num_predict": num_predict},
    )
    return response["message"]["content"]


# ============================================================
# STUDENT MEMORY
# ============================================================

def default_memory():
    return {
        "student": {
            "total_questions": 0,
            "total_quizzes": 0,
            "total_quiz_questions": 0,
            "total_correct": 0
        },
        "topics": {},
        "quiz_history": [],
        "question_history": [],
        "recommendations": [],
        "study_plans": []
    }


def load_memory():
    os.makedirs("storage", exist_ok=True)

    if not os.path.exists(MEMORY_FILE):
        memory = default_memory()
        save_memory(memory)
        return memory

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            memory = json.load(file)

        # Protect against old/incomplete memory files.
        base = default_memory()
        base["student"].update(memory.get("student", {}))
        base["topics"].update(memory.get("topics", {}))
        base["quiz_history"] = memory.get("quiz_history", [])
        base["question_history"] = memory.get("question_history", [])
        base["recommendations"] = memory.get("recommendations", [])
        base["study_plans"] = memory.get("study_plans", [])

        return base

    except (json.JSONDecodeError, OSError):
        memory = default_memory()
        save_memory(memory)
        return memory


def save_memory(memory):
    os.makedirs("storage", exist_ok=True)

    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=2)


def record_question(memory, question, topic):
    """Record a student's study request and track the topic."""
    topic = normalize_topic(topic) or "General"

    memory["student"]["total_questions"] = (
        memory["student"].get("total_questions", 0) + 1
    )

    topic_data = memory["topics"].setdefault(
        topic,
        {
            "attempts": 0,
            "quiz_questions": 0,
            "correct": 0,
            "question_count": 0,
            "last_activity": None
        }
    )

    topic_data["question_count"] = (
        topic_data.get("question_count", 0) + 1
    )
    topic_data["last_activity"] = datetime.now().isoformat(
        timespec="seconds"
    )

    memory["question_history"].append({
        "question": question,
        "topic": topic,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })

    memory["question_history"] = memory["question_history"][-100:]


def record_quiz(memory, topic, score, total, wrong_topics=None):
    """Record quiz results in both overall and per-topic memory."""
    topic = normalize_topic(topic) or "General"
    score = int(score)
    total = int(total)
    wrong_topics = wrong_topics or []

    student = memory["student"]
    student["total_quizzes"] = student.get("total_quizzes", 0) + 1
    student["total_quiz_questions"] = (
        student.get("total_quiz_questions", 0) + total
    )
    student["total_correct"] = (
        student.get("total_correct", 0) + score
    )

    topic_data = memory["topics"].setdefault(
        topic,
        {
            "attempts": 0,
            "quiz_questions": 0,
            "correct": 0,
            "question_count": 0,
            "last_activity": None
        }
    )

    topic_data["attempts"] = topic_data.get("attempts", 0) + 1
    topic_data["quiz_questions"] = (
        topic_data.get("quiz_questions", 0) + total
    )
    topic_data["correct"] = topic_data.get("correct", 0) + score
    topic_data["last_activity"] = datetime.now().isoformat(
        timespec="seconds"
    )

    percentage = (score / total * 100) if total else 0

    memory["quiz_history"].append({
        "type": "quiz",
        "topic": topic,
        "score": score,
        "total": total,
        "percentage": round(percentage, 1),
        "wrong_topics": list(wrong_topics),
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })

    memory["quiz_history"] = memory["quiz_history"][-100:]


def get_topic_accuracy(topic_data):
    """Return topic quiz accuracy as a percentage."""
    total = topic_data.get("quiz_questions", 0)
    correct = topic_data.get("correct", 0)

    if not total:
        return None

    return (correct / total) * 100


def get_weak_topics(memory, limit=5):
    """Return quiz topics with accuracy below 75%, weakest first."""
    items = []

    for topic, data in memory.get("topics", {}).items():
        accuracy = get_topic_accuracy(data)
        if accuracy is None:
            continue

        if accuracy < 75:
            items.append({
                "topic": topic,
                "accuracy": accuracy,
                "attempts": data.get("attempts", 0),
                "quiz_questions": data.get("quiz_questions", 0)
            })

    items.sort(key=lambda item: item["accuracy"])
    return items[:limit]


def get_strong_topics(memory, limit=5):
    """Return quiz topics with accuracy of at least 80%, strongest first."""
    items = []

    for topic, data in memory.get("topics", {}).items():
        accuracy = get_topic_accuracy(data)
        if accuracy is None:
            continue

        if accuracy >= 80:
            items.append({
                "topic": topic,
                "accuracy": accuracy,
                "attempts": data.get("attempts", 0),
                "quiz_questions": data.get("quiz_questions", 0)
            })

    items.sort(key=lambda item: item["accuracy"], reverse=True)
    return items[:limit]


def normalize_topic(topic):
    topic = topic.strip()
    topic = re.sub(r"\s+", " ", topic)

    if len(topic) > 80:
        topic = topic[:80]

    return topic


def extract_topic(question):
    """
    Extract the study topic from common student requests.

    Examples:
      "Give me a quiz on pandas" -> "pandas"
      "Explain CNN in simple terms" -> "CNN"
      "Summarize neural networks" -> "neural networks"
      "Give me an 8 mark answer for ReLU" -> "ReLU"
    """
    text = question.strip()

    patterns = [
        # Quiz / MCQ requests.
        r"(?:give me|create|generate|start)?\s*"
        r"(?:a\s+)?(?:quiz|mcq|multiple[\s-]?choice)"
        r"(?:\s+questions?)?\s+(?:on|about|for)\s+(.+)$",

        # Explanation requests.
        r"(?:explain|teach me)\s+(.+?)"
        r"(?:\s+in\s+(?:simple|easy)\s+(?:terms|language))?$",

        # Summary requests.
        r"(?:summarize|summarise|summary|notes?)\s+"
        r"(?:about|on|for)?\s*(.+)$",

        # Exam requests.
        r"(?:give me|write|create)?\s*"
        r"(?:an?\s+)?\d+\s*[-]?\s*marks?\s+"
        r"(?:answer\s+)?(?:for|on|about)\s+(.+)$",

        r"(?:exam\s+answer)\s+(?:for|on|about)\s+(.+)$",

        # Study plan requests.
        r"(?:study\s+plan|study\s+schedule|revision\s+plan)"
        r"(?:\s+(?:for|on))?\s*(.+)$",

        # Generic "questions about X".
        r"(?:questions?|question)\s+(?:on|about)\s+(.+)$"
    ]

    cleaned = text.rstrip(" ?.!")

    for pattern in patterns:
        match = re.search(
            pattern,
            cleaned,
            re.IGNORECASE
        )

        if match:
            topic = match.group(1).strip()

            # Remove trailing duration from study-plan topics.
            topic = re.sub(
                r"\s+for\s+\d+\s*[-]?\s*days?$",
                "",
                topic,
                flags=re.IGNORECASE
            )

            # Remove common trailing filler.
            topic = re.sub(
                r"\s+in\s+(?:simple|easy)\s+(?:terms|language)$",
                "",
                topic,
                flags=re.IGNORECASE
            )

            return normalize_topic(topic)

    # Fallback: remove common command words.
    fallback = re.sub(
        r"\b(give me|create|generate|please|tell me|"
        r"what is|what are|can you|could you)\b",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    fallback = re.sub(
        r"\s+for\s+\d+\s*[-]?\s*marks?$",
        "",
        fallback,
        flags=re.IGNORECASE
    )

    return normalize_topic(fallback)


# ============================================================
# MARKS EXTRACTION
# ============================================================

def extract_marks(question, default=8):
    match = re.search(
        r"(\d+)\s*[-]?\s*marks?",
        question,
        re.IGNORECASE
    )

    if not match:
        return default

    return max(1, min(int(match.group(1)), 50))




# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent_rules(question):
    """Route obvious requests without relying on the LLM."""
    text = question.strip().lower()

    if re.search(r"\b(quiz|mcq|multiple[\s-]?choice)\b", text):
        return "QUIZ"

    if re.search(
        r"\b(progress|performance|score|scores|accuracy|results)\b",
        text
    ):
        return "PROGRESS"

    if (
        "what should i study next" in text
        or "what should i learn next" in text
        or "recommend" in text
        or "recommendation" in text
        or "next topic" in text
    ):
        return "RECOMMEND"

    if re.search(
        r"\b(study plan|study schedule|revision plan|plan for|plan on)\b",
        text
    ):
        return "PLAN"

    if re.search(
        r"\b(\d+\s*[-]?\s*mark|\d+\s*[-]?\s*marks|exam answer|long answer)\b",
        text
    ):
        return "EXAM"

    if re.search(
        r"\b(summarize|summarise|summary|short notes|study notes|notes on)\b",
        text
    ):
        return "SUMMARIZE"

    if re.search(
        r"\b(explain|explanation|teach me|in simple terms|in simple language)\b",
        text
    ):
        return "EXPLAIN"

    return None


def detect_intent(question):
    """
    Hybrid router:
    - Deterministic rules handle clear requests.
    - Ollama handles genuinely ambiguous requests.
    """
    rule_intent = detect_intent_rules(question)

    if rule_intent:
        return rule_intent

    prompt = f"""
Classify this student request into exactly ONE category:

ASK
EXPLAIN
SUMMARIZE
QUIZ
EXAM
PLAN
PROGRESS
RECOMMEND

Student request:
{question}

Return ONLY the category name.
"""

    result = ask_ollama(prompt).strip().upper()

    categories = [
        "ASK",
        "EXPLAIN",
        "SUMMARIZE",
        "QUIZ",
        "EXAM",
        "PLAN",
        "PROGRESS",
        "RECOMMEND"
    ]

    if result in categories:
        return result

    first_line = result.splitlines()[0].strip() if result else ""

    if first_line in categories:
        return first_line

    return "ASK"


# ============================================================
# TOPIC EXTRACTION
# ============================================================

def extract_topic(question):
    """Extract the topic from common study requests."""
    text = question.strip().rstrip(" ?.!")

    patterns = [
        r"(?:give me|create|generate|start)?\s*"
        r"(?:a\s+)?(?:quiz|mcq|multiple[\s-]?choice)"
        r"(?:\s+questions?)?\s+(?:on|about|for)\s+(.+)$",

        r"(?:explain|teach me)\s+(.+?)"
        r"(?:\s+in\s+(?:simple|easy)\s+(?:terms|language))?$",

        r"(?:summarize|summarise|summary|notes?)\s+"
        r"(?:about|on|for)?\s*(.+)$",

        r"(?:give me|write|create)?\s*"
        r"(?:an?\s+)?\d+\s*[-]?\s*marks?\s+"
        r"(?:answer\s+)?(?:for|on|about)\s+(.+)$",

        r"(?:exam\s+answer)\s+(?:for|on|about)\s+(.+)$",

        r"(?:study\s+plan|study\s+schedule|revision\s+plan)"
        r"(?:\s+(?:for|on))?\s*(.+)$",

        r"(?:questions?|question)\s+(?:on|about)\s+(.+)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            topic = match.group(1).strip()

            topic = re.sub(
                r"\s+for\s+\d+\s*[-]?\s*days?$",
                "",
                topic,
                flags=re.IGNORECASE
            )

            topic = re.sub(
                r"\s+in\s+(?:simple|easy)\s+(?:terms|language)$",
                "",
                topic,
                flags=re.IGNORECASE
            )

            return normalize_topic(topic)

    fallback = re.sub(
        r"\b(give me|create|generate|please|tell me|"
        r"what is|what are|can you|could you)\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    fallback = re.sub(
        r"\s+for\s+\d+\s*[-]?\s*marks?$",
        "",
        fallback,
        flags=re.IGNORECASE
    )

    return normalize_topic(fallback)


# ============================================================
# MARKS EXTRACTION
# ============================================================

def extract_marks(question, default=8):
    match = re.search(
        r"(\d+)\s*[-]?\s*marks?",
        question,
        re.IGNORECASE
    )

    if not match:
        return default

    return max(1, min(int(match.group(1)), 50))


# ============================================================
# EXPLAIN
# ============================================================

def explain_topic(topic, context):
    prompt = f"""
You are StudyAI, a personal AI tutor.

Explain this topic:

{topic}

Use the study material below:

{context}

Explain it in simple language.

Structure:
1. Definition
2. Simple explanation
3. Main points
4. Example
5. Important exam points

Do not invent information that is not in the material.
"""
    return ask_ollama(prompt, num_predict=450, temperature=0.25)


# ============================================================
# SUMMARIZE
# ============================================================

def summarize_topic(topic, context):
    prompt = f"""
You are StudyAI.

Create concise study notes about:

{topic}

Study material:

{context}

Include:
- Definition
- Key concepts
- Important points
- Examples
- Applications
- Advantages/disadvantages if present
- Exam-important points

Use the provided study material as the main source and do not invent unsupported facts.
"""
    return ask_ollama(prompt, num_predict=500, temperature=0.25)


# ============================================================
# EXAM ANSWER
# ============================================================

def generate_exam_answer(question, marks, context):
    prompt = f"""
You are StudyAI helping a college student prepare for exams.

Question:
{question}

Marks:
{marks}

Study material:
{context}

Create an answer suitable for a {marks}-mark college exam.

Use:
- Introduction
- Definition
- Explanation
- Main points
- Examples
- Applications/advantages if relevant
- Conclusion

Use simple language.
Do not invent information outside the provided material.
"""
    return ask_ollama(prompt, num_predict=800, temperature=0.25)


# ============================================================
# STUDY PLAN
# ============================================================

def generate_study_plan(topic, days, weak_topics=None):
    weak_topics = weak_topics or []
    weak_text = ", ".join(weak_topics) if weak_topics else "No weak topics identified yet."

    prompt = f"""
You are StudyAI, a personal study planner.

Create a {days}-day study plan for:
{topic}

The student is preparing for an exam.

Known weak topics from previous practice:
{weak_text}

Prioritize weak topics where relevant, while still covering the requested topic.

For each day provide:
- Topics to study
- Revision
- Practice questions
- Quick review

Keep the plan realistic for a college student.
"""
    return ask_ollama(prompt, num_predict=600, temperature=0.3)


# ============================================================
# DAY EXTRACTION
# ============================================================

def extract_days(question, default=7):
    match = re.search(r"\b(\d{1,2})\s*(?:day|days|d)\b", question, re.IGNORECASE)
    if not match:
        return default
    return max(1, min(int(match.group(1)), 30))


# ============================================================
# GENERAL QUESTION
# ============================================================

def answer_question(question, context):
    prompt = f"""
You are StudyAI, a personal study assistant.

Answer the student's question using the study material.

STUDY MATERIAL:

{context}

QUESTION:

{question}

Rules:

1. Give a clear answer.
2. Use simple language.
3. Use the study material as the main source.
4. Do not invent information.
5. Use examples when useful.
"""

    return ask_ollama(prompt, num_predict=450, temperature=0.25)


# ============================================================
# QUIZ GENERATOR
# ============================================================

def generate_quiz_questions(topic, context, difficulty="mixed", count=5):
    """
    Generate validated MCQs.

    Important: the answer key is normalized here so downstream scoring
    compares the student's choice against a clean A/B/C/D value.
    """
    prompt = f"""
You are StudyAI, an exam quiz generator.

Create exactly {count} multiple-choice questions about:
{topic}

Difficulty:
{difficulty}

Use this study material:
{context}

Return ONLY valid JSON:

[
  {{
    "question": "Question text",
    "options": [
      "A) option",
      "B) option",
      "C) option",
      "D) option"
    ],
    "answer": "A",
    "explanation": "Short explanation",
    "topic": "specific concept tested"
  }}
]

Rules:
- Base questions only on the study material.
- Each question must have exactly four options.
- The answer MUST be exactly one of A, B, C, D.
- Do not put the correct answer into the question text.
- Do not add markdown or text outside the JSON.
"""

    response = ask_ollama(prompt, num_predict=750, temperature=0.1)

    try:
        start_json = response.find("[")
        end_json = response.rfind("]") + 1

        if start_json == -1 or end_json <= start_json:
            raise ValueError("No JSON array found")

        questions = json.loads(response[start_json:end_json])

        if not isinstance(questions, list):
            raise ValueError("Quiz response is not a list")

        valid_questions = []

        for item in questions:
            if not isinstance(item, dict):
                continue

            question_text = str(item.get("question", "")).strip()
            options = item.get("options", [])
            answer = str(item.get("answer", "")).strip().upper()

            if not question_text or not isinstance(options, list):
                continue

            if len(options) != 4:
                continue

            if answer not in {"A", "B", "C", "D"}:
                continue

            # Normalize options so the UI always receives A-D in order.
            normalized_options = []
            for index, option in enumerate(options):
                label = "ABCD"[index]
                option_text = str(option).strip()

                # Remove an existing A)/B)/C)/D) prefix and rebuild it.
                option_text = re.sub(
                    r"^[A-Da-d]\s*[\)\.:\-]\s*",
                    "",
                    option_text
                ).strip()

                normalized_options.append(f"{label}) {option_text}")

            valid_questions.append({
                "question": question_text,
                "options": normalized_options,
                "answer": answer,
                "explanation": str(item.get("explanation", "")).strip(),
                "topic": normalize_topic(
                    str(item.get("topic", topic))
                ) or normalize_topic(topic),
            })

        return valid_questions[:count]

    except Exception:
        print("\nCould not create the quiz correctly.")
        print("Raw response:")
        print(response)
        return []

# ============================================================
# ADAPTIVE DIFFICULTY
# ============================================================

def choose_quiz_difficulty(memory, topic):
    topic = normalize_topic(topic)

    if topic not in memory["topics"]:
        return "mixed"

    data = memory["topics"][topic]

    if data["attempts"] == 0:
        return "mixed"

    accuracy = get_topic_accuracy(data)

    if accuracy < 50:
        return "easy"
    elif accuracy < 75:
        return "medium"
    else:
        return "hard"



# ============================================================
# AUTONOMOUS LEARNING LOOP
# ============================================================

def identify_weak_concepts(wrong_topics):
    """
    Remove duplicates and keep the order in which weak concepts
    appeared during the quiz.
    """
    concepts = []

    for topic in wrong_topics:
        topic = normalize_topic(topic)

        if topic and topic not in concepts:
            concepts.append(topic)

    return concepts


def generate_targeted_questions(topic, context, count=3):
    """
    Generate practice questions specifically for a concept the
    student missed in the quiz.
    """
    prompt = f"""
You are StudyAI's adaptive learning agent.

The student answered a quiz question incorrectly about:

{topic}

Relevant study material:
{context}

Create exactly {count} targeted multiple-choice practice questions
that help the student understand and practice this specific concept.

Return ONLY valid JSON:

[
  {{
    "question": "Question text",
    "options": [
      "A) option",
      "B) option",
      "C) option",
      "D) option"
    ],
    "answer": "A",
    "explanation": "Short explanation",
    "topic": "{topic}"
  }}
]

Rules:
- Base the questions only on the provided study material.
- Focus specifically on the weak concept.
- Start with easier questions.
- Each question must have exactly four options.
- The answer must be A, B, C or D.
- Do not add markdown or text outside the JSON.
"""

    response = ask_ollama(prompt, num_predict=650, temperature=0.2)

    try:
        start = response.find("[")
        end = response.rfind("]") + 1

        if start == -1 or end <= start:
            raise ValueError("No JSON array found")

        questions = json.loads(response[start:end])

        valid_questions = []

        for question in questions:
            if not isinstance(question, dict):
                continue

            options = question.get("options", [])
            answer = str(
                question.get("answer", "")
            ).strip().upper()

            if (
                "question" not in question
                or len(options) != 4
                or answer not in ["A", "B", "C", "D"]
            ):
                continue

            question["answer"] = answer
            question["topic"] = normalize_topic(
                str(question.get("topic", topic))
            )

            valid_questions.append(question)

        return valid_questions

    except Exception:
        print("\nCould not create targeted practice questions.")
        return []


def autonomous_explain_weak_concept(topic, context):
    """
    Automatically teach the concept the student missed.
    """
    prompt = f"""
You are StudyAI's adaptive tutor.

The student struggled with this concept:

{topic}

Relevant study material:
{context}

Teach this concept again in very simple language.

Use this structure:

1. What it means
2. Simple explanation
3. Key points
4. Small example
5. Common mistake to avoid
6. One exam tip

Stay within the supplied study material.
Do not invent information.
"""

    return ask_ollama(prompt, num_predict=350, temperature=0.25)


def run_targeted_practice(topic, questions):
    """
    Optional mini-practice generated by the autonomous agent.
    """
    if not questions:
        return 0, 0

    print("\n" + "-" * 65)
    print(f"TARGETED PRACTICE: {topic}")
    print("-" * 65)

    score = 0

    for number, question in enumerate(questions, start=1):
        print(f"\nPractice {number}/{len(questions)}")
        print(question["question"])
        print()

        for option in question["options"]:
            print(option)

        while True:
            answer = input(
                "\nYour answer (A/B/C/D): "
            ).strip().upper()

            if answer in ["A", "B", "C", "D"]:
                break

            print("Please enter A, B, C or D.")

        correct = question["answer"]

        if answer == correct:
            print("Correct! ✅")
            score += 1
        else:
            print(f"Not quite. Correct answer: {correct} ❌")

        print(
            f"Explanation: "
            f"{question.get('explanation', '')}"
        )

    return score, len(questions)


def run_autonomous_learning_loop(
    wrong_topics,
    database,
    memory
):
    """
    Autonomous loop:

    Quiz mistakes
        ↓
    Identify weak concepts
        ↓
    Retrieve relevant PDF content
        ↓
    Teach the weak concept
        ↓
    Generate targeted practice
        ↓
    Test the student again
        ↓
    Update memory
        ↓
    Recommend next action
    """
    weak_concepts = identify_weak_concepts(wrong_topics)

    if not weak_concepts:
        print("\n🤖 No weak concepts detected.")
        print("The agent will continue monitoring future quizzes.")
        return

    print("\n" + "=" * 65)
    print("              AUTONOMOUS LEARNING AGENT")
    print("=" * 65)

    print("\nThe agent detected these weak concepts:")

    for concept in weak_concepts:
        print(f"  • {concept}")

    # Process only the first two concepts in one cycle so the
    # terminal session does not become overwhelming.
    for concept in weak_concepts[:2]:
        print("\n" + "=" * 65)
        print(f"🤖 ADAPTIVE TUTOR → {concept}")
        print("=" * 65)

        # Step 1: retrieve relevant material from the existing RAG system.
        print("\n🔎 Retrieving relevant study material...")
        results = search_pdf(concept, database)
        context = build_context(results)

        # Step 2: automatically explain the weak concept.
        print("\n📚 Reviewing the weak concept...")
        explanation = autonomous_explain_weak_concept(
            concept,
            context
        )

        print("\n" + "-" * 65)
        print("ADAPTIVE EXPLANATION")
        print("-" * 65)
        print(explanation)

        # Step 3: create targeted practice.
        print("\n📝 Generating targeted practice...")
        targeted_questions = generate_targeted_questions(
            concept,
            context,
            count=3
        )

        if not targeted_questions:
            continue

        # Step 4: let the student practice.
        practice_score, practice_total = run_targeted_practice(
            concept,
            targeted_questions
        )

        # Step 5: record the targeted practice separately.
        if practice_total:
            percentage = (
                practice_score /
                practice_total
            ) * 100

            # The weak concept can be more specific than the original
            # quiz topic (for example, "Boolean"). Make sure a topic
            # record exists before updating targeted-practice fields.
            normalized_concept = normalize_topic(concept) or "General"
            topic_data = memory["topics"].setdefault(
                normalized_concept,
                {
                    "attempts": 0,
                    "quiz_questions": 0,
                    "correct": 0,
                    "question_count": 0,
                    "last_activity": None
                }
            )

            topic_data["last_targeted_score"] = round(
                percentage,
                1
            )

            topic_data["targeted_attempts"] = (
                topic_data.get(
                    "targeted_attempts",
                    0
                ) + practice_total
            )

            topic_data["targeted_correct"] = (
                topic_data.get(
                    "targeted_correct",
                    0
                ) + practice_score
            )

            memory["quiz_history"].append({
                "type": "targeted_practice",
                "topic": normalized_concept,
                "score": practice_score,
                "total": practice_total,
                "percentage": round(percentage, 1),
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                )
            })

            memory["quiz_history"] = memory[
                "quiz_history"
            ][-50:]

            save_memory(memory)

            print("\n" + "-" * 65)
            print("TARGETED PRACTICE RESULT")
            print("-" * 65)
            print(
                f"Score: {practice_score}/{practice_total}"
            )
            print(
                f"Percentage: {percentage:.1f}%"
            )

            if percentage >= 80:
                print(
                    "✅ Concept improved. The agent will "
                    "increase difficulty later."
                )
            elif percentage >= 60:
                print(
                    "🟡 Better, but one more revision "
                    "would be useful."
                )
            else:
                print(
                    "🔴 This concept still needs attention."
                )

    # Step 6: update the personalized recommendation.
    print("\n🤖 Updating your learning recommendation...")
    recommendation = generate_recommendation(memory)

    print("\n" + "-" * 65)
    print("NEXT STUDY ACTION")
    print("-" * 65)
    print(recommendation)

    print("\n" + "=" * 65)
    print("Autonomous learning cycle completed. 🤖")
    print("=" * 65)


# ============================================================
# INTERACTIVE QUIZ
# ============================================================

def run_quiz(topic, context, memory, database):
    print("\n" + "=" * 65)
    print("                       QUIZ MODE")
    print("=" * 65)

    difficulty = choose_quiz_difficulty(memory, topic)

    print(f"\nAdaptive difficulty: {difficulty.upper()}")
    print("Generating your quiz...")

    questions = generate_quiz_questions(
        topic,
        context,
        difficulty=difficulty,
        count=5
    )

    if not questions:
        return

    score = 0
    total = len(questions)
    wrong_topics = []

    for number, question in enumerate(
        questions,
        start=1
    ):
        print("\n" + "-" * 65)
        print(f"Question {number}/{total}")
        print(f"Difficulty: {difficulty.upper()}")
        print()

        print(question["question"])
        print()

        for option in question["options"]:
            print(option)

        while True:
            answer = input(
                "\nYour answer (A/B/C/D): "
            ).strip().upper()

            if answer in ["A", "B", "C", "D"]:
                break

            print("Please enter A, B, C or D.")

        # Deterministic scoring: compare only the normalized answer key.
        correct_answer = str(
            question.get("answer", "")
        ).strip().upper()

        answer = str(answer).strip().upper()

        question_topic = question.get("topic", topic)

        if answer == correct_answer:
            print("\nCorrect! ✅")
            score += 1
        else:
            print("\nWrong ❌")
            print(f"Correct answer: {correct_answer}")
            wrong_topics.append(question_topic)

        print(
            f"Explanation: "
            f"{question.get('explanation', '')}"
        )

    percentage = (
        score / total
    ) * 100

    # Keep the quiz result separate from the AI recommendation.
    quiz_result = {
        "topic": topic,
        "score": score,
        "total": total,
        "percentage": round(percentage, 1),
        "wrong_topics": identify_weak_concepts(wrong_topics),
    }

    record_quiz(
        memory,
        topic,
        score,
        total,
        wrong_topics
    )

    save_memory(memory)

    print("\n" + "=" * 65)
    print("                    QUIZ RESULT")
    print("=" * 65)

    print(f"\nTopic: {topic}")
    print(f"Score: {score}/{total}")
    print(f"Percentage: {percentage:.1f}%")

    if percentage >= 80:
        print("\nExcellent! 🔥")
        print("The next quiz can increase the difficulty.")
    elif percentage >= 60:
        print("\nGood job! 👍")
        print("Review the topic and try another quiz.")
    else:
        print("\nKeep practicing! 📚")
        print("The agent will create targeted practice.")

    if wrong_topics:
        print("\nConcepts missed in this quiz:")
        for item in identify_weak_concepts(wrong_topics):
            print(f"  • {item}")

        # ----------------------------------------------------
        # AUTONOMOUS LEARNING LOOP
        # ----------------------------------------------------
        run_autonomous_learning_loop(
            wrong_topics,
            database,
            memory
        )

    else:
        print("\n🎉 You answered every question correctly!")
        print("The agent will consider increasing difficulty.")

    print("=" * 65)


# ============================================================
# PERFORMANCE ANALYZER
# ============================================================

def show_progress(memory):
    print("\n" + "=" * 65)
    print("                  STUDENT PROGRESS")
    print("=" * 65)

    student = memory["student"]

    total_questions = student["total_quiz_questions"]
    total_correct = student["total_correct"]

    overall_accuracy = (
        total_correct / total_questions * 100
        if total_questions
        else 0
    )

    print(f"\nTotal questions asked: {student['total_questions']}")
    print(f"Total quizzes: {student['total_quizzes']}")
    print(f"Quiz questions attempted: {total_questions}")
    print(f"Overall quiz accuracy: {overall_accuracy:.1f}%")

    weak = get_weak_topics(memory)
    strong = get_strong_topics(memory)

    print("\nWeak Topics:")

    if weak:
        for item in weak:
            print(
                f"  • {item['topic']} "
                f"→ {item['accuracy']:.1f}%"
            )
    else:
        print("  No quiz performance available yet.")

    print("\nStrong Topics:")

    if strong:
        for item in strong:
            print(
                f"  • {item['topic']} "
                f"→ {item['accuracy']:.1f}%"
            )
    else:
        print("  No strong topics identified yet.")

    print("=" * 65)


# ============================================================
# RECOMMENDATION AGENT
# ============================================================

def generate_recommendation(memory):
    weak = get_weak_topics(memory, limit=5)
    strong = get_strong_topics(memory, limit=5)

    weak_text = "\n".join(
        f"- {item['topic']}: {item['accuracy']:.1f}%"
        for item in weak
    )

    strong_text = "\n".join(
        f"- {item['topic']}: {item['accuracy']:.1f}%"
        for item in strong
    )

    recent_history = memory["quiz_history"][-10:]

    prompt = f"""
You are StudyAI's personalized learning agent.

Analyze the student's study performance.

WEAK TOPICS:
{weak_text or "- No weak topics available yet"}

STRONG TOPICS:
{strong_text or "- No strong topics available yet"}

RECENT QUIZ HISTORY:
{json.dumps(recent_history, indent=2)}

Give a practical recommendation for the student's next study session.

Include:

1. Priority topic
2. Why it should be studied
3. What to do first
4. Practice recommendation
5. Suggested next quiz difficulty

Use only the performance data provided.
"""

    recommendation = ask_ollama(prompt, num_predict=280, temperature=0.2)

    memory["recommendations"].append({
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })

    memory["recommendations"] = memory["recommendations"][-20:]
    save_memory(memory)

    return recommendation


def show_recommendation(memory):
    print("\n" + "=" * 65)
    print("             PERSONALIZED STUDY RECOMMENDATION")
    print("=" * 65)

    recommendation = generate_recommendation(memory)
    print("\n" + recommendation)

    print("=" * 65)


# ============================================================
# AGENT MEMORY SUMMARY
# ============================================================

def memory_summary(memory):
    print("\n" + "=" * 65)
    print("                    MEMORY SUMMARY")
    print("=" * 65)

    print("\nTopics tracked:")

    if memory["topics"]:
        for topic, data in memory["topics"].items():
            accuracy = get_topic_accuracy(data)

            if accuracy is None:
                accuracy_text = "No quiz data"
            else:
                accuracy_text = f"{accuracy:.1f}%"

            print(
                f"  • {topic} | "
                f"Attempts: {data['attempts']} | "
                f"Accuracy: {accuracy_text}"
            )
    else:
        print("  No topics tracked yet.")

    print("=" * 65)


# ============================================================
# MAIN AGENT
# ============================================================


# ============================================================
# AUTONOMOUS AGENT DECISION ENGINE
# ============================================================

def choose_next_action(memory):
    """
    Decide the next learning action from student performance.

    Priority:
      1. Weak topics -> targeted remediation
      2. Recently weak targeted practice -> retry
      3. Topics not reviewed recently -> revision
      4. Strong topics -> increase difficulty
      5. No history -> start a discovery/review session
    """
    weak = get_weak_topics(memory)
    strong = get_strong_topics(memory)

    # Weak-topic remediation has the highest priority.
    if weak:
        return {
            "action": "REMEDIATION",
            "topic": weak[0]["topic"],
            "reason": "This topic currently needs more practice."
        }

    # Look for a topic that has had targeted practice but still
    # has a low targeted score.
    for topic, data in memory.get("topics", {}).items():
        targeted_score = data.get("last_targeted_score")
        if targeted_score is not None and targeted_score < 75:
            return {
                "action": "TARGETED_RETRY",
                "topic": topic,
                "reason": "The latest targeted practice score is below 75%."
            }

    # If the student has strong topics, use them for harder practice.
    if strong:
        return {
            "action": "ADVANCED_PRACTICE",
            "topic": strong[0]["topic"],
            "reason": "Recent performance is strong, so difficulty can increase."
        }

    # Fall back to any known topic.
    topics = list(memory.get("topics", {}).keys())
    if topics:
        return {
            "action": "REVIEW",
            "topic": topics[0],
            "reason": "Reviewing a known topic is the next available action."
        }

    return {
        "action": "DISCOVERY",
        "topic": "general",
        "reason": "There is not enough learning history yet."
    }


def show_agent_decision(memory):
    decision = choose_next_action(memory)

    print("\n" + "=" * 65)
    print("                 AGENT DECISION ENGINE")
    print("=" * 65)
    print(f"Next action : {decision['action']}")
    print(f"Topic       : {decision['topic']}")
    print(f"Reason      : {decision['reason']}")
    print("=" * 65)

    return decision


def run_closed_loop_session(memory, database):
    """
    Closed-loop autonomous learning:
      observe -> decide -> retrieve -> teach/practice -> evaluate -> update
    """
    print("\n" + "=" * 65)
    print("              CLOSED-LOOP AUTONOMOUS SESSION")
    print("=" * 65)

    decision = show_agent_decision(memory)
    topic = decision["topic"]

    # If the topic is known, retrieve material and teach it first.
    if topic != "general":
        print(f"\n🤖 Agent selected: {topic}")
        print("🔎 Retrieving relevant study material...")

        context = search_pdf(topic, database)

        if context:
            print("\n📚 Quick adaptive review:")
            try:
                explanation = explain_topic(topic, context)
                print(explanation)
            except Exception as exc:
                print(f"Could not generate the review: {exc}")
        else:
            print("No matching material was found in the study PDF.")

        print("\n📝 Starting adaptive practice...")
        try:
            run_quiz(topic, context or "")
        except Exception as exc:
            print(f"Practice session ended with an error: {exc}")

    else:
        print("\n🤖 Not enough history yet.")
        print("Start with a topic-specific quiz to build your learning profile.")

    # Reload memory because the quiz may have changed it.
    latest_memory = load_memory()

    print("\n" + "=" * 65)
    print("             NEXT AGENT DECISION")
    print("=" * 65)

    next_decision = choose_next_action(latest_memory)
    print(f"Action : {next_decision['action']}")
    print(f"Topic  : {next_decision['topic']}")
    print(f"Why    : {next_decision['reason']}")
    print("=" * 65)

    save_memory(latest_memory)
    return next_decision



# ============================================================
# ADAPTIVE STUDY PLANNER
# ============================================================

def _planner_priority(memory):
    """Select the next topic using the student's stored performance."""

    topics = memory.get("topics", {})

    # Find quiz topics below 75%, weakest first.
    candidates = []

    for topic, data in topics.items():
        accuracy = get_topic_accuracy(data)

        if accuracy is not None and accuracy < 75:
            candidates.append((topic, accuracy))

    if candidates:
        candidates.sort(key=lambda item: item[1])

        topic, accuracy = candidates[0]

        return {
            "topic": topic,
            "type": "weak_topic",
            "accuracy": round(accuracy, 1),
            "reason": f"{topic} needs more practice because the current quiz accuracy is {accuracy:.1f}%."
        }

    # Find topics with recent targeted practice below 75%.
    targeted = []

    for topic, data in topics.items():
        score = data.get("last_targeted_score")

        if score is not None and score < 75:
            targeted.append((topic, score))

    if targeted:
        targeted.sort(key=lambda item: item[1])

        topic, score = targeted[0]

        return {
            "topic": topic,
            "type": "targeted_practice",
            "accuracy": round(float(score), 1),
            "reason": f"{topic} needs another targeted-practice session."
        }

    # Find the topic that has been inactive for the longest time.
    if topics:
        def activity_key(item):
            value = item[1].get("last_activity")
            return value or ""

        topic, data = min(topics.items(), key=activity_key)
        accuracy = get_topic_accuracy(data)

        return {
            "topic": topic,
            "type": "revision",
            "accuracy": round(accuracy, 1) if accuracy is not None else 0,
            "reason": f"{topic} is a known topic that can be revised to maintain retention."
        }

    return {
        "topic": "general",
        "type": "discovery",
        "accuracy": 0,
        "reason": "There is not enough quiz history yet, so the plan starts with general discovery and learning."
    }


def create_adaptive_study_plan(memory, days=1, minutes_per_day=60):
    """
    Create and save a deterministic adaptive study plan.

    The planner uses the student's existing memory and does not require
    an additional Ollama generation call.
    """

    days = max(1, min(int(days), 30))
    minutes_per_day = max(15, min(int(minutes_per_day), 480))

    priority = _planner_priority(memory)

    priority_topic = priority["topic"]
    priority_type = priority["type"]
    priority_accuracy = priority["accuracy"]

    days_plan = []

    for day in range(1, days + 1):

        if priority_type == "weak_topic":
            review = max(5, int(minutes_per_day * 0.20))
            learn = max(10, int(minutes_per_day * 0.30))
            practice = max(10, int(minutes_per_day * 0.35))
            assess = minutes_per_day - review - learn - practice

            tasks = [
                {
                    "type": "review",
                    "topic": priority_topic,
                    "minutes": review,
                    "description": f"Review the fundamentals of {priority_topic}."
                },
                {
                    "type": "learn",
                    "topic": priority_topic,
                    "minutes": learn,
                    "description": f"Study important concepts and examples in {priority_topic}."
                },
                {
                    "type": "practice",
                    "topic": priority_topic,
                    "minutes": practice,
                    "description": f"Practice questions focused on {priority_topic}."
                },
                {
                    "type": "assess",
                    "topic": priority_topic,
                    "minutes": assess,
                    "description": f"Take a short assessment on {priority_topic}."
                }
            ]

        elif priority_type == "targeted_practice":
            review = max(5, int(minutes_per_day * 0.20))
            practice = max(15, int(minutes_per_day * 0.45))
            advanced = max(10, int(minutes_per_day * 0.20))
            assess = minutes_per_day - review - practice - advanced

            tasks = [
                {
                    "type": "review",
                    "topic": priority_topic,
                    "minutes": review,
                    "description": f"Quickly revise {priority_topic}."
                },
                {
                    "type": "practice",
                    "topic": priority_topic,
                    "minutes": practice,
                    "description": f"Solve targeted problems in {priority_topic}."
                },
                {
                    "type": "advanced",
                    "topic": priority_topic,
                    "minutes": advanced,
                    "description": f"Attempt more challenging {priority_topic} problems."
                },
                {
                    "type": "assess",
                    "topic": priority_topic,
                    "minutes": assess,
                    "description": f"Measure your progress in {priority_topic}."
                }
            ]

        elif priority_type == "revision":
            review = max(10, int(minutes_per_day * 0.30))
            practice = max(15, int(minutes_per_day * 0.40))
            advanced = max(5, int(minutes_per_day * 0.20))
            assess = minutes_per_day - review - practice - advanced

            tasks = [
                {
                    "type": "review",
                    "topic": priority_topic,
                    "minutes": review,
                    "description": f"Revise previously learned {priority_topic} concepts."
                },
                {
                    "type": "practice",
                    "topic": priority_topic,
                    "minutes": practice,
                    "description": f"Practice problems related to {priority_topic}."
                },
                {
                    "type": "advanced",
                    "topic": priority_topic,
                    "minutes": advanced,
                    "description": f"Explore advanced applications of {priority_topic}."
                },
                {
                    "type": "assess",
                    "topic": priority_topic,
                    "minutes": assess,
                    "description": f"Test your understanding of {priority_topic}."
                }
            ]

        else:
            discovery = max(10, int(minutes_per_day * 0.25))
            learn = max(15, int(minutes_per_day * 0.35))
            practice = max(10, int(minutes_per_day * 0.25))
            assess = minutes_per_day - discovery - learn - practice

            tasks = [
                {
                    "type": "discover",
                    "topic": "general",
                    "minutes": discovery,
                    "description": "Explore topics available in the uploaded study material."
                },
                {
                    "type": "learn",
                    "topic": "general",
                    "minutes": learn,
                    "description": "Learn important concepts from the study material."
                },
                {
                    "type": "practice",
                    "topic": "general",
                    "minutes": practice,
                    "description": "Practice questions based on the study material."
                },
                {
                    "type": "assess",
                    "topic": "general",
                    "minutes": assess,
                    "description": "Take a short assessment to identify strengths and weaknesses."
                }
            ]

        # Safety: ensure the displayed task total is exactly the requested time.
        total = sum(int(task["minutes"]) for task in tasks)
        if total != minutes_per_day:
            tasks[-1]["minutes"] += minutes_per_day - total

        days_plan.append({
            "day": day,
            "total_minutes": minutes_per_day,
            "tasks": tasks
        })

    supporting_topics = [
        topic for topic in memory.get("topics", {}).keys()
        if topic != priority_topic
    ][:3]

    plan = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "days": days,
        "minutes_per_day": minutes_per_day,
        "priority_topic": priority_topic,
        "priority_type": priority_type,
        "priority_accuracy": priority_accuracy,
        "reason": priority["reason"],
        "days_plan": days_plan,
        "supporting_topics": supporting_topics
    }

    if "study_plans" not in memory:
        memory["study_plans"] = []

    memory["study_plans"].append(plan)
    memory["study_plans"] = memory["study_plans"][-20:]

    save_memory(memory)

    return plan


def get_latest_study_plan(memory):
    """Return the latest saved adaptive study plan, if available."""
    plans = memory.get("study_plans", [])

    if not plans:
        return None

    return plans[-1]


def show_adaptive_study_plan(memory, days=1, minutes_per_day=60):
    """Display an adaptive study plan in the terminal."""

    plan = create_adaptive_study_plan(
        memory,
        days=days,
        minutes_per_day=minutes_per_day
    )

    print("\n" + "=" * 65)
    print("              ADAPTIVE STUDY PLAN")
    print("=" * 65)

    print(f"\nPriority topic : {plan['priority_topic']}")
    print(f"Priority type  : {plan['priority_type']}")
    print(f"Accuracy       : {plan['priority_accuracy']}%")
    print(f"Study time     : {plan['minutes_per_day']} minutes/day")
    print(f"Reason         : {plan['reason']}")

    for day_plan in plan["days_plan"]:
        print("\n" + "-" * 65)
        print(f"DAY {day_plan['day']}  |  {day_plan['total_minutes']} minutes")
        print("-" * 65)

        for task in day_plan["tasks"]:
            print(
                f"  • {task['type'].upper():10} "
                f"{task['minutes']:>3} min | "
                f"{task['topic']} | "
                f"{task['description']}"
            )

    if plan["supporting_topics"]:
        print("\nSupporting topics:")
        for topic in plan["supporting_topics"]:
            print(f"  • {topic}")

    print("=" * 65)

    return plan

def main():
    print("=" * 65)
    print("                    STUDY AI AGENT")
    print("=" * 65)

    # --------------------------------------------------------
    # Check PDF
    # --------------------------------------------------------

    if not os.path.exists(PDF_FILE):
        print("\nPDF not found!")
        print(f"Put your PDF here:\n{PDF_FILE}")
        return

    # --------------------------------------------------------
    # Load student memory
    # --------------------------------------------------------

    memory = load_memory()

    print("\nStudent memory loaded.")

    # --------------------------------------------------------
    # Load vector database
    # --------------------------------------------------------

    if os.path.exists(_vector_file()):
        print("\nLoading existing vector database...")
        database = load_vector_database()
        print(f"Loaded {len(database)} chunks.")

    else:
        print("\nLoading PDF...")
        pages = load_pdf()
        print(f"Loaded {len(pages)} pages.")

        print("\nCreating chunks...")
        chunks = create_chunks(pages)
        print(f"Created {len(chunks)} chunks.")

        build_vector_database(chunks)
        database = load_vector_database()

    # --------------------------------------------------------
    # Ready
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("StudyAI is ready! 🤖")
    print("=" * 65)

    print("""
You can ask naturally:

  Explain CNN in simple terms
  What is backpropagation?
  Summarize neural networks
  Give me a quiz on CNN
  Give me an 8 mark answer for ReLU
  Create a 7 day study plan for Deep Learning

New agent capabilities:

  Show my progress
  What should I study next?
  Show my memory
  Start autonomous study session

Type 'exit' to quit.
""")

    print("=" * 65)

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    while True:
        question = input("\nYou: ").strip()

        if question.lower() == "exit":
            print("\nGood luck with your studies! 📚")
            break

        if not question:
            continue

        # ----------------------------------------------------
        # Special local commands
        # ----------------------------------------------------

        if question.lower() in [
            "show progress",
            "progress",
            "my progress"
        ]:
            show_progress(memory)
            continue

        if question.lower() in [
            "show memory",
            "memory",
            "memory summary"
        ]:
            memory_summary(memory)
            continue

        if question.lower() in [
            "recommend",
            "recommendation",
            "what should i study next?",
            "what should i study next"
        ]:
            show_recommendation(memory)
            continue

        # ----------------------------------------------------
        # Autonomous study session
        # ----------------------------------------------------

        if question.lower() in [
            "start autonomous study",
            "start autonomous study session",
            "autonomous study",
            "let the agent decide",
            "study for me",
            "start learning session"
        ]:
            run_autonomous_study_session(database, memory)
            continue

        # ----------------------------------------------------
        # Detect intent
        # ----------------------------------------------------

        print("\n🤔 Understanding your request...")
        # Direct commands for the autonomous decision engine.
        command_lower = question.strip().lower()

        if command_lower in {
            "show agent decision",
            "what should the agent do next",
            "decide my next action",
            "agent decision"
        }:
            memory = load_memory()
            show_agent_decision(memory)
            continue

        if command_lower in {
            "start closed loop session",
            "start closed-loop session",
            "run autonomous learning",
            "start autonomous learning session",
            "autonomous learning loop"
        }:
            memory = load_memory()
            run_closed_loop_session(memory, database)
            continue

        intent = detect_intent(question)
        topic = extract_topic(question)
        print(f"Agent mode: {intent}")
        print(f"Detected topic: {topic}")

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if intent == "PROGRESS":
            show_progress(memory)
            continue

        # ----------------------------------------------------
        # Recommendation
        # ----------------------------------------------------

        if intent == "RECOMMEND":
            show_recommendation(memory)
            continue

        # ----------------------------------------------------
        # Study plan
        # ----------------------------------------------------

        if intent == "PLAN":
            print("\n🤖 Creating personalized study plan...")

            days = extract_days(question)
            topic = extract_topic(question)

            weak_topics = [
                item["topic"]
                for item in get_weak_topics(memory)
            ]

            answer = generate_study_plan(
                topic,
                days,
                weak_topics
            )

            record_question(
                memory,
                question,
                topic
            )
            save_memory(memory)

            print("\n" + "=" * 65)
            print("STUDY AI")
            print("=" * 65)
            print(answer)
            continue

        # ----------------------------------------------------
        # Search PDF
        # ----------------------------------------------------

        print("\n🔎 Searching study material...")

        results = search_pdf(
            question,
            database
        )

        context = build_context(results)

        # ----------------------------------------------------
        # Topic + memory
        # ----------------------------------------------------

        record_question(
            memory,
            question,
            topic
        )

        save_memory(memory)

        # ----------------------------------------------------
        # Quiz
        # ----------------------------------------------------

        if intent == "QUIZ":
            run_quiz(
                topic,
                context,
                memory,
                database
            )
            continue

        # ----------------------------------------------------
        # Other agent functions
        # ----------------------------------------------------

        print("🤖 Generating answer...")

        if intent == "EXPLAIN":
            answer = explain_topic(
                question,
                context
            )

        elif intent == "SUMMARIZE":
            answer = summarize_topic(
                question,
                context
            )

        elif intent == "EXAM":
            marks = extract_marks(question)

            answer = generate_exam_answer(
                question,
                marks,
                context
            )

        else:
            answer = answer_question(
                question,
                context
            )

        # ----------------------------------------------------
        # Display answer
        # ----------------------------------------------------

        print("\n" + "=" * 65)
        print("STUDY AI")
        print("=" * 65)
        print(answer)

        show_sources(results)


# ============================================================
# SOURCES
# ============================================================

def show_sources(results):
    pages = sorted(
        set(
            result["page"]
            for result in results
        )
    )

    print("\nSources:")

    for page in pages:
        print(f"  📄 Page {page}")


# ============================================================
# AUTONOMOUS STUDY SESSION
# ============================================================

def choose_autonomous_topic(memory):
    """Choose the next topic without requiring the student to name one."""
    weak = get_weak_topics(memory, limit=1)
    if weak:
        return weak[0]["topic"], "weak_topic"

    # If there are no weak topics, revisit the least recently active
    # known topic. This prevents the agent from repeatedly choosing
    # the same strong topic.
    topics = memory.get("topics", {})
    if topics:
        def activity_key(item):
            value = item[1].get("last_activity")
            return value or ""

        topic = sorted(topics.items(), key=activity_key)[0][0]
        return topic, "review"

    return "General", "starter"


def run_autonomous_study_session(database, memory):
    """
    Let the agent decide the next learning action from student memory.

    Decision loop:
      performance -> topic -> retrieval -> teaching -> adaptive quiz
                     -> memory update -> recommendation
    """
    print("\n" + "=" * 65)
    print("              AUTONOMOUS STUDY SESSION")
    print("=" * 65)

    topic, reason = choose_autonomous_topic(memory)

    if reason == "weak_topic":
        print(f"\n🤖 I selected '{topic}' because it is currently a weak topic.")
    elif reason == "review":
        print(f"\n🤖 I selected '{topic}' for spaced review.")
    else:
        print("\n🤖 No quiz history yet. I will start with a general study session.")

    print("\n🔎 Retrieving relevant study material...")
    results = search_pdf(topic, database)
    context = build_context(results)

    if not context.strip():
        print("\n⚠️ I could not find enough material for this topic.")
        print("Try asking about a topic that exists in your PDF.")
        return

    print("\n📚 Teaching the selected topic...")
    explanation = autonomous_explain_weak_concept(topic, context)

    print("\n" + "-" * 65)
    print("AUTONOMOUS LESSON")
    print("-" * 65)
    print(explanation)

    print("\n📝 Creating an adaptive check...")
    difficulty = choose_quiz_difficulty(memory, topic)
    questions = generate_quiz_questions(
        topic,
        context,
        difficulty=difficulty,
        count=5
    )

    if questions:
        score = 0
        wrong_topics = []
        total = len(questions)

        print("\n" + "=" * 65)
        print(f"AUTONOMOUS QUIZ — {difficulty.upper()}")
        print("=" * 65)

        for number, question in enumerate(questions, start=1):
            print("\n" + "-" * 65)
            print(f"Question {number}/{total}")
            print(question["question"])
            print()

            for option in question["options"]:
                print(option)

            while True:
                answer = input("\nYour answer (A/B/C/D): ").strip().upper()
                if answer in ["A", "B", "C", "D"]:
                    break
                print("Please enter A, B, C or D.")

            correct = question["answer"].strip().upper()
            question_topic = question.get("topic", topic)

            if answer == correct:
                score += 1
                print("Correct! ✅")
            else:
                wrong_topics.append(question_topic)
                print(f"Not quite. Correct answer: {correct} ❌")

            print(f"Explanation: {question.get('explanation', '')}")

        record_quiz(memory, topic, score, total, wrong_topics)
        save_memory(memory)

        percentage = (score / total) * 100
        print("\n" + "=" * 65)
        print("AUTONOMOUS SESSION RESULT")
        print("=" * 65)
        print(f"Topic: {topic}")
        print(f"Score: {score}/{total}")
        print(f"Percentage: {percentage:.1f}%")

        if wrong_topics:
            print("\n🤖 I found concepts that need more attention:")
            for concept in identify_weak_concepts(wrong_topics):
                print(f"  • {concept}")
        else:
            print("\n🎉 No mistakes detected in this session.")

        print("\n🤖 Updating your next action...")
        print(generate_recommendation(memory))
    else:
        print("\n⚠️ I could not generate a quiz for this topic.")

    save_memory(memory)
    print("\n🤖 Autonomous study session completed.")



# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    main()
