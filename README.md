# 🤖 Study AI Agent

> An AI-powered personalized learning platform that combines **RAG, local LLMs, adaptive learning, autonomous agents, voice interaction, analytics, and per-user memory** into a single study dashboard.

**Study AI Agent** is a full-stack AI learning assistant designed to help students understand study materials, generate adaptive quizzes, track learning progress, create personalized study plans, and interact with an AI tutor.

The system uses a **React/Vite frontend**, **FastAPI backend**, **Ollama local LLM**, and a **Retrieval-Augmented Generation (RAG)** pipeline to provide context-aware responses from uploaded learning materials.

---

## ✨ Features

### 🧑‍🏫 AI Tutor
- Ask questions about study materials
- Context-aware answers using RAG
- Conversational interaction
- Persistent learning context

### 📚 Multi-Document RAG
- Load and process PDF learning materials
- Split documents into searchable chunks
- Generate embeddings
- Retrieve relevant context before generating answers
- Support learning from multiple documents

### 📝 Adaptive Quiz
- Generate quizzes from study material
- Adaptive question generation
- Automatic answer evaluation
- Quiz scoring
- Learning-memory updates based on performance

### 📊 Learning Analytics
Track learning activity including:

- Overall accuracy
- Questions answered
- Quizzes completed
- Strong topics
- Weak topics
- Learning progress
- AI-generated recommendations

### 📅 Personalized Study Planner
Creates study recommendations based on:

- Learning progress
- Weak topics
- Previous performance
- Study history

### 🤖 Autonomous Study Agent
The agent can make study decisions based on the learner's current state.

It can:

- Analyze learning progress
- Identify weak areas
- Recommend what to study next
- Start autonomous study sessions
- Perform adaptive review
- Generate practice activities

### 🛠️ Agent Tool Calling

The agent can execute specialized study tools based on the user's request.

Example workflow:

```text
User Request
     ↓
Agent
     ↓
Tool Selection
     ↓
Tool Execution
     ↓
Result
     ↓
AI Response
```

### 🎙️ Voice Interface
- Voice input for interacting with the AI tutor
- Voice interaction within agent tools
- Browser-based speech capabilities

### 📒 Smart Notes
Automatically generate structured notes from learning content and AI interactions.

### 🔐 Authentication
- User registration and login
- Password hashing
- Authentication tokens
- Protected API routes
- Per-user learning data
- Per-user memory

Each user gets an independent learning context instead of sharing the same study history.

---

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │      Student        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   React + Vite UI   │
                    │                     │
                    │ Dashboard           │
                    │ AI Tutor            │
                    │ Quiz                │
                    │ Progress            │
                    │ Planner             │
                    │ Agent Tools         │
                    │ Smart Notes         │
                    │ Voice               │
                    └──────────┬──────────┘
                               │
                         REST API / HTTP
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    │                     │
                    │ Authentication      │
                    │ Study APIs          │
                    │ Quiz Engine         │
                    │ Agent Engine        │
                    │ Memory              │
                    │ Analytics           │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │ RAG /       │ │ Study Agent │ │ User Memory │
        │ Vector DB   │ │             │ │             │
        └──────┬──────┘ └──────┬──────┘ └─────────────┘
               │               │
               └───────┬───────┘
                       ▼
              ┌─────────────────┐
              │     Ollama       │
              │   Local LLM      │
              └─────────────────┘
```

---

## 🧠 RAG Pipeline

The study assistant uses Retrieval-Augmented Generation to ground responses in the student's learning material.

```text
PDF / Documents
      ↓
Document Loading
      ↓
Text Extraction
      ↓
Chunking
      ↓
Embeddings
      ↓
Vector Storage
      ↓
User Question
      ↓
Similarity Retrieval
      ↓
Relevant Context
      ↓
Ollama LLM
      ↓
Context-Aware Answer
```

This allows the assistant to answer questions using the student's actual study material instead of relying only on general model knowledge.

---

## 🛠️ Technology Stack

### Frontend

- React
- Vite
- JavaScript
- Axios
- CSS

### Backend

- Python
- FastAPI
- Uvicorn
- REST APIs

### AI / Machine Learning

- Ollama
- Local LLM
- Retrieval-Augmented Generation (RAG)
- Embeddings
- Vector search
- Agent-based workflows

### Data & Storage

- SQLite
- JSON-based learning memory
- Local vector storage
- PDF document processing

### Authentication & Security

- Password hashing
- HMAC-based authentication tokens
- Protected API endpoints
- Per-user memory isolation

---

## 📁 Project Structure

```text
study-ai-agent/
│
├── backend/
│   ├── api_server.py
│   ├── study_agent.py
│   ├── requirements.txt
│   ├── data/
│   └── storage/
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

Install:

- Python 3.10+
- Node.js
- npm
- Ollama

Make sure Ollama is running locally.

Check:

```bash
ollama list
```

---

## ⚙️ Backend Setup

Open a terminal inside the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
uvicorn api_server:app --reload --port 8000
```

The backend will run at:

```text
http://localhost:8000
```

---

## 🦙 Ollama Setup

Install Ollama and make sure the required model is available.

For example:

```bash
ollama pull llama3.2
```

Verify:

```bash
ollama list
```

Then keep Ollama running while using the application.

---

## ⚛️ Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open the URL shown by Vite, typically:

```text
http://localhost:5173
```

---

## 🔄 Example User Flow

```text
Register / Login
       ↓
Upload / Load Study Material
       ↓
Document Processing
       ↓
Chunking + Embeddings
       ↓
Vector Storage
       ↓
Ask AI Tutor
       ↓
Retrieve Relevant Context
       ↓
Generate Answer with Ollama
       ↓
Track Learning Activity
       ↓
Analyze Strengths / Weaknesses
       ↓
Generate Adaptive Quiz
       ↓
Update Learning Memory
       ↓
Recommend Next Study Activity
```

---

## 🎯 What Makes This Project Different

Instead of implementing only a chatbot, the project combines several AI capabilities into one learning system:

```text
Chatbot
   +
RAG
   +
Memory
   +
Adaptive Learning
   +
Quiz Generation
   +
Analytics
   +
Planning
   +
Autonomous Agent
   +
Tool Calling
   +
Voice
   +
Authentication
```

The goal is to move from a simple **question-answering chatbot** toward an **AI learning agent that can understand a student's progress and decide what learning activity should happen next**.

---

## 🔮 Future Improvements

Potential future enhancements include:

- Cloud deployment
- PostgreSQL database
- Production-grade authentication
- Streaming LLM responses
- More advanced vector databases
- Additional document formats
- Automatic flashcard generation
- Spaced-repetition scheduling
- Learning streaks and gamification
- Teacher/admin dashboard
- Multi-language learning support
- Model selection between multiple local/cloud LLMs

---

## 📸 Screenshots

Add screenshots of the application here:

```text
Dashboard
AI Tutor
Quiz
Progress
Agent Tools
Smart Notes
Login
```

Example:

```markdown
![Dashboard](screenshots/dashboard.png)
```

---

## 📌 Project Highlights

- Full-stack AI application
- Local LLM integration using Ollama
- Retrieval-Augmented Generation
- Vector-based document retrieval
- Adaptive quiz generation
- Autonomous AI agent
- Agent tool calling
- Personalized learning recommendations
- Voice interaction
- Authentication and user isolation
- Learning analytics
- React + FastAPI architecture

---

## 👨‍💻 Author

**Vadde Bhargav**

MCA Student | Software Development & AI Enthusiast

Interested in:

- Java
- Python
- Spring Boot
- AI/ML
- Generative AI
- RAG
- AI Agents
- Full-Stack Development

---

## ⭐ If You Find This Project Useful

Consider giving the repository a star and exploring the project.

**Repository:**  
https://github.com/mechomen/study-ai-agent