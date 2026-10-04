# StudyAI Agent 🤖

An AI-powered personalized learning platform that combines
Retrieval-Augmented Generation (RAG), Large Language Models,
student memory, adaptive learning, quizzes, analytics, and
autonomous study planning into a single application.

## 🌐 Live Demo

https://study-ai-agent-n1xa7hkbc-bhargavbabu30-gmailcoms-projects.vercel.app

## 💻 GitHub

https://github.com/mechomen/study-ai-agent

---

## 📌 Project Overview

StudyAI Agent is designed to act as a personalized AI study assistant.

Instead of behaving like a general-purpose chatbot, the system uses
the student's study material and learning history to provide
context-aware explanations, track progress, identify weak areas,
recommend what to study next, and generate personalized learning plans.

The project was built as a full-stack AI application with a React
frontend, FastAPI backend, RAG pipeline, LLM integration,
authentication, and cloud deployment.

---

## ✨ Key Features

### 1. AI Tutor

Students can ask questions about their study material and receive
AI-generated explanations based on the relevant learning content.

Examples:

- Explain CNN in simple terms
- What is backpropagation?
- Summarize neural networks
- Explain ReLU with an example
- Give an exam-oriented answer

---

### 2. PDF-Based RAG

StudyAI can process study documents and use them as the knowledge
source for answering questions.

The RAG pipeline performs:

PDF → Page Extraction → Text Chunking → Embeddings → Vector Search
→ Relevant Context → LLM Response

This helps the AI generate responses grounded in the student's
uploaded study material rather than relying only on general model
knowledge.

---

### 3. Embeddings and Vector Search

The application converts document chunks into embeddings and stores
them in a local vector database.

When the student asks a question, the system searches for the most
relevant chunks and provides them to the language model as context.

The deployed version uses FastEmbed for embedding generation.

---

### 4. Personalized Student Memory

StudyAI maintains learning information for individual users.

The memory system can track information such as:

- Topics studied
- Quiz attempts
- Correct answers
- Accuracy
- Weak topics
- Strong topics
- Learning activity
- Study history

This information is used to make future learning recommendations
more personalized.

---

### 5. Adaptive Quiz System

The system can generate multiple-choice quizzes based on a selected
topic and the available study material.

Quiz difficulty can adapt according to the student's previous
performance.

The system also records quiz results and identifies concepts where
the student needs additional practice.

---

### 6. Learning Analytics

The dashboard provides an overview of the student's learning progress.

It can display:

- Overall quiz accuracy
- Number of quizzes
- Questions attempted
- Correct answers
- Topic-wise performance
- Weak topics
- Strong topics
- Recent quiz history
- Recommended next action

---

### 7. Adaptive Study Planning

StudyAI can create personalized study plans based on the student's
learning history.

The planning system considers the student's progress and weak areas
to determine what should be studied next.

---

### 8. Autonomous Learning Agent

One of the main goals of the project was to move beyond a simple
chatbot.

The agent can analyze the student's learning state and decide the
next learning action.

The autonomous learning flow can:

1. Analyze student memory
2. Identify the next topic
3. Retrieve relevant study material
4. Generate a review
5. Start adaptive practice
6. Record the result
7. Update student memory
8. Decide the next learning action

This creates a closed learning loop instead of isolated AI responses.

---

### 9. User Authentication

The backend includes user registration and login functionality.

Authentication includes:

- User registration
- Login
- Password hashing
- Token-based authentication
- Protected API endpoints
- User-specific learning data

---

## 🏗️ System Architecture

```text
                    ┌─────────────────────┐
                    │      React UI       │
                    │      Vite           │
                    └──────────┬──────────┘
                               │
                               │ REST API
                               ▼
                    ┌─────────────────────┐
                    │     FastAPI         │
                    │      Backend        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       Authentication      Study Agent       Memory
              │                │                │
              │                ▼                │
              │        RAG / Vector Search      │
              │                │                │
              │                ▼                │
              │             LLM                │
              │                │                │
              └────────────────┼────────────────┘
                               │
                               ▼
                     Personalized Response
