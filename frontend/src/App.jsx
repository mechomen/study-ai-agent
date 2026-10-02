import React, { useEffect, useMemo, useState } from "react";
import {
  getDashboard,
  getStudyPlan,
  askQuestion,
  startQuiz,
  submitQuiz,
  startAutonomousSession,
  uploadPdf,
  executeAgentAction,
  generateSmartNotes,
  loginUser,
  registerUser,
  getCurrentUser,
  logoutUser,
} from "./api";
import "./styles.css";

function StatCard({ icon, label, value, suffix = "" }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">
          {value ?? 0}<span>{suffix}</span>
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ value = 0 }) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${safe}%` }} />
    </div>
  );
}

function TopicCard({ topic, accuracy, onPractice, busy }) {
  const value = Number(accuracy ?? 0);
  return (
    <div className="topic-card">
      <div className="topic-card-top">
        <div>
          <span className="topic-kicker">TOPIC</span>
          <h3>{topic}</h3>
        </div>
        <strong>{accuracy == null ? "—" : `${accuracy}%`}</strong>
      </div>
      <ProgressBar value={value} />
      <button className="text-button" onClick={() => onPractice(topic)} disabled={busy}>
        Practice topic <span>→</span>
      </button>
    </div>
  );
}

function PlanTask({ task, index, onClick }) {
  const icons = ["📖", "🧠", "✍️", "🎯"];
  return (
    <button className="plan-task" onClick={onClick}>
      <span className="plan-task-icon">{icons[index] || "•"}</span>
      <span className="plan-task-copy">
        <strong>{task.activity || task.task || "Study"}</strong>
        <small>
          {task.minutes ?? task.duration ?? 0} min
          {task.description ? ` · ${task.description}` : ""}
        </small>
      </span>
      <span className="plan-step">{index + 1}</span>
    </button>
  );
}

function getOptionEntries(options) {
  if (Array.isArray(options)) {
    return options.map((value, index) => [
      ["A", "B", "C", "D"][index] || String(index + 1),
      value,
    ]);
  }
  return Object.entries(options || {});
}

function cleanRecommendation(text) {
  if (!text) return "";
  return String(text)
    .replace(/\*\*/g, "")
    .replace(/^#+\s*/gm, "")
    .replace(/\r/g, "")
    .trim();
}

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authenticated, setAuthenticated] = useState(
    () => Boolean(localStorage.getItem("studyai_token"))
  );
  const [authLoading, setAuthLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);

  const [activeView, setActiveView] = useState("dashboard");
  const [mobileNav, setMobileNav] = useState(false);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [sourcePages, setSourcePages] = useState([]);

  const [quizTopic, setQuizTopic] = useState("");
  const [quiz, setQuiz] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [quizResult, setQuizResult] = useState(null);

  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState(false);

  const [studyPlan, setStudyPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploadError, setUploadError] = useState("");

  const [agentAction, setAgentAction] = useState("auto");
  const [agentQuestion, setAgentQuestion] = useState("");
  const [agentTopic, setAgentTopic] = useState("");
  const [agentResult, setAgentResult] = useState(null);
  const [agentBusy, setAgentBusy] = useState(false);

  const [smartNotesTopic, setSmartNotesTopic] = useState("");
  const [smartNotes, setSmartNotes] = useState(null);
  const [smartNotesBusy, setSmartNotesBusy] = useState(false);
  const [smartNotesSpeaking, setSmartNotesSpeaking] = useState(false);

  async function refresh() {
    try {
      setError("");
      const res = await getDashboard();
      setData(res);
    } catch (e) {
      console.error("Dashboard error:", e);
      setError(
        e?.response?.data?.detail ||
          "Could not connect to the FastAPI backend. Start it on port 8000."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadStudyPlan() {
    try {
      setPlanLoading(true);
      const result = await getStudyPlan(1, 60);
      setStudyPlan(result);
    } catch (e) {
      console.error("Study plan error:", e);
    } finally {
      setPlanLoading(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function initializeAuth() {
      const token = localStorage.getItem("studyai_token");

      if (!token) {
        if (active) {
          setAuthenticated(false);
          setAuthLoading(false);
          setLoading(false);
        }
        return;
      }

      try {
        const result = await getCurrentUser();
        if (!active) return;
        setCurrentUser(result?.user || null);
        setAuthenticated(true);
      } catch (e) {
        localStorage.removeItem("studyai_token");
        localStorage.removeItem("studyai_user");
        if (active) {
          setAuthenticated(false);
          setCurrentUser(null);
        }
      } finally {
        if (active) setAuthLoading(false);
      }
    }

    initializeAuth();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    refresh();
    loadStudyPlan();
  }, [authenticated]);

  const topics = useMemo(() => data?.topics ?? [], [data]);
  const student = data?.student ?? {};
  const decision = data?.decision ?? {};
  const recommendation = cleanRecommendation(data?.recommendation);

  const priorityTopic =
    studyPlan?.priority_topic || decision?.topic || "general";

  const priorityAccuracy =
    studyPlan?.priority_accuracy ??
    (priorityTopic !== "general"
      ? topics.find(
          (item) =>
            String(item.topic).toLowerCase() ===
            String(priorityTopic).toLowerCase()
        )?.accuracy
      : null);

  function navigate(view) {
    setActiveView(view);
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleLogin(credentials) {
    setAuthLoading(true);
    setError("");

    try {
      const result = await loginUser(credentials.email, credentials.password);
      localStorage.setItem("studyai_token", result.token);
      localStorage.setItem("studyai_user", JSON.stringify(result.user));
      setCurrentUser(result.user);
      setAuthenticated(true);
    } catch (e) {
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          "Login failed."
      );
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleRegister(details) {
    setAuthLoading(true);
    setError("");

    try {
      const result = await registerUser(
        details.name,
        details.email,
        details.password
      );
      localStorage.setItem("studyai_token", result.token);
      localStorage.setItem("studyai_user", JSON.stringify(result.user));
      setCurrentUser(result.user);
      setAuthenticated(true);
    } catch (e) {
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          "Registration failed."
      );
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    try {
      if (localStorage.getItem("studyai_token")) {
        await logoutUser();
      }
    } catch (e) {
      console.warn("Logout request failed:", e);
    } finally {
      localStorage.removeItem("studyai_token");
      localStorage.removeItem("studyai_user");
      setCurrentUser(null);
      setAuthenticated(false);
      setData(null);
    }
  }

  async function handleAsk(e) {
    e?.preventDefault();
    if (!question.trim()) return;

    const currentQuestion = question.trim();
    setBusy(true);
    setError("");

    try {
      const result = await askQuestion(
        currentQuestion,
        chatHistory.slice(-8)
      );
      const nextAnswer =
        result?.answer || "No answer was returned by the agent.";

      setAnswer(nextAnswer);
      setSourcePages(result?.source_pages || []);
      setChatHistory((prev) => [
        ...prev,
        { role: "user", text: currentQuestion },
        { role: "assistant", text: nextAnswer },
      ]);
      setQuestion("");
      await refresh();
    } catch (e) {
      console.error("Ask error:", e);
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          "The agent could not answer that question."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleQuizStart(topicOverride) {
    const topic = (topicOverride || quizTopic).trim();

    if (!topic) {
      setError("Please enter a topic for the quiz.");
      return;
    }

    setBusy(true);
    setError("");
    setQuizResult(null);

    try {
      const res = await startQuiz(topic, 5);
      setQuiz(res);
      setAnswers(Array(res?.questions?.length || 0).fill(""));
      setQuizTopic(topic);
      setActiveView("quiz");
      setTimeout(() => {
        document.getElementById("quiz-section")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 50);
    } catch (e) {
      console.error("Quiz error:", e);
      setError(
        e?.response?.data?.detail ||
          "Quiz generation failed. Check Ollama and the vector database."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleQuizSubmit() {
    if (!quiz) return;

    if (
      answers.length !== quiz.questions.length ||
      answers.some((a) => !a)
    ) {
      setError("Please answer every question.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const res = await submitQuiz(quiz.quiz_id, answers);
      setQuizResult(res);
      setQuiz(null);
      setAnswers([]);
      await refresh();
      await loadStudyPlan();
    } catch (e) {
      console.error("Quiz submit error:", e);
      setError(
        e?.response?.data?.detail || "Could not submit the quiz."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAutonomous() {
    setBusy(true);
    setError("");

    try {
      const res = await startAutonomousSession();
      setSession(res);

      if (res?.topic && res.topic !== "general") {
        setQuizTopic(res.topic);
      }

      await refresh();
      await loadStudyPlan();
    } catch (e) {
      console.error("Autonomous session error:", e);
      setError(
        e?.response?.data?.detail ||
          "Could not start the autonomous session."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAgentExecute() {
    if (agentAction === "search" && !agentQuestion.trim()) {
      setError("Enter a search query for the Search Documents tool.");
      return;
    }
    if (["explain", "summarize", "exam", "quiz", "plan"].includes(agentAction) && !agentTopic.trim() && !agentQuestion.trim()) {
      setError("Enter a topic or question for the selected tool.");
      return;
    }

    setAgentBusy(true);
    setError("");
    try {
      const result = await executeAgentAction({
        action: agentAction,
        topic: agentTopic,
        question: agentQuestion,
        days: 1,
        minutesPerDay: 60,
      });
      setAgentResult(result);
      await refresh();
      await loadStudyPlan();
    } catch (e) {
      console.error("Agent tool error:", e);
      setError(e?.response?.data?.detail || e?.message || "Agent tool execution failed.");
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleGenerateSmartNotes(topicOverride) {
    const topic = (topicOverride || smartNotesTopic).trim();
    if (!topic) {
      setError("Enter a topic to generate smart notes.");
      return;
    }

    setSmartNotesBusy(true);
    setError("");
    try {
      const result = await generateSmartNotes(topic);
      setSmartNotes(result);
      setSmartNotesTopic(result?.topic || topic);
    } catch (e) {
      console.error("Smart notes error:", e);
      setError(e?.response?.data?.detail || e?.message || "Could not generate smart notes.");
    } finally {
      setSmartNotesBusy(false);
    }
  }

  function speakSmartNotes() {
    if (!smartNotes?.notes || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(smartNotes.notes);
    utterance.lang = "en-IN";
    utterance.rate = 0.92;
    utterance.onstart = () => setSmartNotesSpeaking(true);
    utterance.onend = () => setSmartNotesSpeaking(false);
    utterance.onerror = () => setSmartNotesSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }

  function stopSmartNotesSpeech() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setSmartNotesSpeaking(false);
  }

  async function handleStartTodayPlan() {
    const priority = studyPlan?.priority_topic;
    if (priority && priority !== "general") {
      await handleQuizStart(priority);
      return;
    }
    await handleAutonomous();
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    setUploadStatus("");
    setUploadError("");

    if (file && file.type !== "application/pdf") {
      setUploadError("Please select a PDF file.");
      setSelectedFile(null);
    }
  }

  async function handleUploadPdf() {
    if (!selectedFile) {
      setUploadError("Please choose a PDF file first.");
      return;
    }

    setBusy(true);
    setUploadStatus("Uploading and processing PDF...");
    setUploadError("");
    setError("");

    try {
      const result = await uploadPdf(selectedFile);
      setUploadStatus(
        `✓ ${result.message || "PDF processed successfully"} · ${
          result.pages ?? 0
        } pages · ${result.chunks ?? 0} chunks`
      );
      setSelectedFile(null);

      const input = document.getElementById("pdf-upload-input");
      if (input) input.value = "";

      await refresh();
      await loadStudyPlan();
    } catch (e) {
      console.error("PDF upload error:", e);
      const message =
        e?.response?.data?.detail ||
        e?.message ||
        "PDF upload failed.";
      setUploadError(message);
      setUploadStatus("");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-orb">✦</div>
        <h2>StudyAI</h2>
        <p>Checking your account...</p>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <AuthView
        onLogin={handleLogin}
        onRegister={handleRegister}
        error={error}
        clearError={() => setError("")}
      />
    );
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-orb">✦</div>
        <h2>StudyAI</h2>
        <p>Preparing your learning workspace...</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">✦</div>
          <div>
            <strong>StudyAI</strong>
            <span>Adaptive learning</span>
          </div>
        </div>

        <div className="sidebar-section">
          <span className="sidebar-label">WORKSPACE</span>
          <button className={activeView === "dashboard" ? "nav-item active" : "nav-item"} onClick={() => navigate("dashboard")}>
            <span>⌂</span> Dashboard
          </button>
          <button className={activeView === "tutor" ? "nav-item active" : "nav-item"} onClick={() => navigate("tutor")}>
            <span>✦</span> AI Tutor
          </button>
          <button className={activeView === "materials" ? "nav-item active" : "nav-item"} onClick={() => navigate("materials")}>
            <span>▤</span> Materials
          </button>
          <button className={activeView === "materials" ? "nav-item active" : "nav-item"} onClick={() => navigate("materials")}>
            <span>▣</span>
            <div><strong>Materials</strong><small>Study PDFs</small></div>
          </button>
          <button className={activeView === "notes" ? "nav-item active" : "nav-item"} onClick={() => navigate("notes")}>
            <span>📝</span>
            <div><strong>Smart Notes</strong><small>AI-generated notes</small></div>
          </button>
          <button className={activeView === "quiz" ? "nav-item active" : "nav-item"} onClick={() => navigate("quiz")}>
            <span>✓</span> Quiz
          </button>
          <button className={activeView === "progress" ? "nav-item active" : "nav-item"} onClick={() => navigate("progress")}>
            <span>◒</span> Progress
          </button>
          <button className={activeView === "agent" ? "nav-item active" : "nav-item"} onClick={() => navigate("agent")}>
            <span>⚡</span> Agent Tools
          </button>
        </div>

        <div className="sidebar-focus">
          <span>AI FOCUS</span>
          <strong>{priorityTopic}</strong>
          <small>
            {priorityAccuracy == null
              ? "Take a quiz to personalize your path."
              : `${priorityAccuracy}% current accuracy`}
          </small>
          <button onClick={handleStartTodayPlan} disabled={busy}>
            Start focus →
          </button>
        </div>

        <div className="sidebar-bottom">
          <div className="agent-status">
            <span className="status-dot" />
            <span>AI Agent Online</span>
          </div>
          <button className="nav-item">
            <span>⚙</span> Settings
          </button>
        </div>
      </aside>

      {mobileNav && (
        <button className="mobile-overlay" onClick={() => setMobileNav(false)} />
      )}

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}>☰</button>
          <div className="breadcrumb">
            <span>StudyAI</span>
            <b>/</b>
            <strong>
              {activeView === "dashboard"
                ? "Dashboard"
                : activeView === "tutor"
                ? "AI Tutor"
                : activeView === "materials"
                ? "Study Materials"
                : activeView === "quiz"
                ? "Quiz"
                : activeView === "agent"
                ? "Agent Tools"
                : "Progress"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="online-pill"><i /> Agent online</span>
            {currentUser && (
              <div className="user-menu">
                <span className="user-avatar">
                  {(currentUser.name || "U").charAt(0).toUpperCase()}
                </span>
                <span className="user-name">{currentUser.name}</span>
                <button className="logout-button" onClick={handleLogout}>
                  Logout
                </button>
              </div>
            )}
            <button className="top-session" onClick={handleAutonomous} disabled={busy}>
              {busy ? "Working..." : "Run AI Session"}
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError("")}>×</button>
          </div>
        )}

        <div className="content">
          {activeView === "dashboard" && (
            <DashboardView
              data={data}
              student={student}
              topics={topics}
              priorityTopic={priorityTopic}
              priorityAccuracy={priorityAccuracy}
              recommendation={recommendation}
              analytics={data?.analytics || {}}
              recentQuizzes={data?.recent_quizzes || []}
              studyPlan={studyPlan}
              planLoading={planLoading}
              busy={busy}
              onAsk={() => navigate("tutor")}
              onQuiz={handleQuizStart}
              onStartPlan={handleStartTodayPlan}
              onRefreshPlan={loadStudyPlan}
              onMaterials={() => navigate("materials")}
            />
          )}

          {activeView === "tutor" && (
            <TutorView
              question={question}
              setQuestion={setQuestion}
              answer={answer}
              chatHistory={chatHistory}
              sourcePages={sourcePages}
              busy={busy}
              onAsk={handleAsk}
              onClearChat={() => {
                setChatHistory([]);
                setAnswer("");
                setSourcePages([]);
              }}
              onQuiz={(topic) => {
                setQuizTopic(topic);
                handleQuizStart(topic);
              }}
              priorityTopic={priorityTopic}
            />
          )}

          {activeView === "materials" && (
            <MaterialsView
              selectedFile={selectedFile}
              uploadStatus={uploadStatus}
              uploadError={uploadError}
              busy={busy}
              onFileChange={handleFileChange}
              onUpload={handleUploadPdf}
              onAsk={() => navigate("tutor")}
            />
          )}

          {activeView === "notes" && (
            <SmartNotesView
              topic={smartNotesTopic}
              setTopic={setSmartNotesTopic}
              result={smartNotes}
              busy={smartNotesBusy}
              speaking={smartNotesSpeaking}
              onGenerate={handleGenerateSmartNotes}
              onSpeak={speakSmartNotes}
              onStop={stopSmartNotesSpeech}
              topics={topics}
              onTopic={handleGenerateSmartNotes}
            />
          )}

          {activeView === "quiz" && (
            <QuizView
              quizTopic={quizTopic}
              setQuizTopic={setQuizTopic}
              quiz={quiz}
              answers={answers}
              setAnswers={setAnswers}
              quizResult={quizResult}
              busy={busy}
              onStart={handleQuizStart}
              onSubmit={handleQuizSubmit}
              onPractice={handleQuizStart}
              topics={topics}
              priorityTopic={priorityTopic}
            />
          )}

          {activeView === "agent" && (
            <AgentToolsView
              action={agentAction}
              setAction={setAgentAction}
              question={agentQuestion}
              setQuestion={setAgentQuestion}
              topic={agentTopic}
              setTopic={setAgentTopic}
              result={agentResult}
              busy={agentBusy}
              onExecute={handleAgentExecute}
            />
          )}

          {activeView === "progress" && (
            <ProgressView
              student={student}
              topics={topics}
              strongTopics={data?.strong_topics || []}
              weakTopics={data?.weak_topics || []}
              analytics={data?.analytics || {}}
              recentQuizzes={data?.recent_quizzes || []}
              onPractice={handleQuizStart}
              busy={busy}
            />
          )}

          {session && (
            <section className="session-toast">
              <div>
                <span className="section-kicker">AUTONOMOUS SESSION</span>
                <h3>{session?.topic || session?.decision?.topic || "Learning session"}</h3>
                <p>{session?.message || session?.review || "Your agent created a new learning action."}</p>
              </div>
              {session?.topic && session.topic !== "general" && (
                <button className="primary-button" onClick={() => handleQuizStart(session.topic)} disabled={busy}>
                  Start practice →
                </button>
              )}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}


function AuthView({ onLogin, onRegister, error, clearError }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    clearError();

    if (!email.trim() || !password) return;

    if (mode === "register") {
      if (!name.trim()) return;
      if (password.length < 6) return;
      if (password !== confirmPassword) {
        return;
      }
    }

    setBusy(true);
    try {
      if (mode === "login") {
        await onLogin({ email, password });
      } else {
        await onRegister({ name, email, password });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark">✦</div>
          <div>
            <strong>StudyAI</strong>
            <span>Adaptive learning</span>
          </div>
        </div>

        <div className="auth-heading">
          <span className="section-kicker">YOUR LEARNING SPACE</span>
          <h1>{mode === "login" ? "Welcome back." : "Create your account."}</h1>
          <p>
            {mode === "login"
              ? "Sign in to continue your personalized learning journey."
              : "Create an account to keep your StudyAI workspace private and personalized."}
          </p>
        </div>

        {error && (
          <div className="auth-error">
            <span>{error}</span>
            <button type="button" onClick={clearError}>×</button>
          </div>
        )}

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Full name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
                required
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={6}
              required
            />
          </label>

          {mode === "register" && (
            <label>
              Confirm password
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                autoComplete="new-password"
                minLength={6}
                required
              />
            </label>
          )}

          {mode === "register" && password && confirmPassword && password !== confirmPassword && (
            <small className="auth-field-error">Passwords do not match.</small>
          )}

          <button className="primary-button auth-submit" disabled={busy}>
            {busy
              ? "Please wait..."
              : mode === "login"
                ? "Sign in →"
                : "Create account →"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? "New to StudyAI?" : "Already have an account?"}
          <button
            type="button"
            onClick={() => {
              clearError();
              setMode(mode === "login" ? "register" : "login");
            }}
          >
            {mode === "login" ? "Create account" : "Sign in"}
          </button>
        </div>

        <div className="auth-note">
          🔒 Your account is protected with password hashing and session tokens.
        </div>
      </div>
    </div>
  );
}

function DashboardView({
  data,
  student,
  topics,
  priorityTopic,
  priorityAccuracy,
  recommendation,
  analytics,
  recentQuizzes,
  studyPlan,
  planLoading,
  busy,
  onAsk,
  onQuiz,
  onStartPlan,
  onRefreshPlan,
  onMaterials,
}) {
  return (
    <div className="page">
      <section className="welcome-row">
        <div>
          <span className="section-kicker">PERSONAL LEARNING DASHBOARD</span>
          <h1>Learn at your own pace.</h1>
          <p>StudyAI watches your progress and helps you decide what to study next.</p>
        </div>
        <div className="welcome-actions">
          <button className="secondary-button" onClick={onAsk}>Ask StudyAI</button>
          <button className="primary-button" onClick={onStartPlan} disabled={busy}>
            {busy ? "Working..." : "Start today's focus →"}
          </button>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard icon="◒" label="Learning accuracy" value={student.accuracy ?? 0} suffix="%" />
        <StatCard icon="✓" label="Quizzes completed" value={student.total_quizzes ?? 0} />
        <StatCard icon="◎" label="Questions answered" value={student.total_questions ?? 0} />
        <StatCard icon="◷" label="Quiz questions" value={student.quiz_questions ?? 0} />
      </section>

      <section className="focus-layout">
        <div className="focus-card">
          <div className="focus-copy">
            <span className="section-kicker light">RECOMMENDED NEXT STEP</span>
            <h2>{priorityTopic}</h2>
            <p>
              {recommendation ||
                decisionText(data?.decision) ||
                "Complete a quiz and StudyAI will personalize your next learning step."}
            </p>
            <div className="focus-meta">
              <span>{priorityAccuracy == null ? "No score yet" : `${priorityAccuracy}% accuracy`}</span>
              <span>•</span>
              <span>Adaptive practice</span>
            </div>
            <button className="light-button" onClick={() => onQuiz(priorityTopic)} disabled={busy || priorityTopic === "general"}>
              Practice {priorityTopic} →
            </button>
          </div>
          <div className="focus-orbit">
            <div className="orbit-ring one" />
            <div className="orbit-ring two" />
            <div className="orbit-core">✦</div>
          </div>
        </div>

        <div className="quick-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon">⚡</span>
              <div>
                <h3>Quick actions</h3>
                <p>Jump straight into learning</p>
              </div>
            </div>
          </div>
          <button onClick={onAsk}><span>✦</span><b>Ask AI</b><small>Ask from your material</small><em>→</em></button>
          <button onClick={() => onQuiz(priorityTopic)} disabled={priorityTopic === "general" || busy}><span>✓</span><b>Priority quiz</b><small>Practice your focus topic</small><em>→</em></button>
          <button onClick={onMaterials}><span>↑</span><b>Add material</b><small>Upload a new PDF</small><em>→</em></button>
        </div>
      </section>

      <section className="analytics-grid">
        <div className="white-card analytics-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon purple">↗</span>
              <div>
                <h3>Recent performance</h3>
                <p>Your latest quiz scores</p>
              </div>
            </div>
            <span className={`trend-badge ${(analytics?.change_vs_previous ?? 0) >= 0 ? "up" : "down"}`}>
              {(analytics?.change_vs_previous ?? 0) >= 0 ? "↑" : "↓"} {Math.abs(analytics?.change_vs_previous ?? 0)} pts
            </span>
          </div>
          {recentQuizzes?.length ? (
            <div className="score-bars">
              {[...recentQuizzes].slice(0, 7).reverse().map((quizItem, index) => (
                <div className="score-bar-item" key={`${quizItem.timestamp || index}-${index}`}>
                  <div className="score-bar-track">
                    <div style={{ height: `${Math.max(5, Math.min(100, Number(quizItem.percentage) || 0))}%` }} />
                  </div>
                  <b>{Math.round(Number(quizItem.percentage) || 0)}%</b>
                  <span>{quizItem.topic || "Quiz"}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-box">Complete a few quizzes to see your performance trend.</div>
          )}
        </div>

        <div className="white-card analytics-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon blue">✦</span>
              <div>
                <h3>Learning momentum</h3>
                <p>Simple signals from your activity</p>
              </div>
            </div>
          </div>
          <div className="momentum-grid">
            <div><b>{analytics?.recent_average ?? 0}%</b><span>Recent average</span></div>
            <div><b>{analytics?.quiz_streak ?? 0}</b><span>Quiz streak</span></div>
            <div><b>{student.correct ?? 0}</b><span>Correct answers</span></div>
            <div><b>{topics.length}</b><span>Tracked topics</span></div>
          </div>
        </div>
      </section>

      <section className="two-column">
        <div className="white-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon purple">▣</span>
              <div>
                <h3>Today's study path</h3>
                <p>Personalized from your recent performance</p>
              </div>
            </div>
            <button className="icon-button" onClick={onRefreshPlan} disabled={planLoading}>↻</button>
          </div>

          {planLoading ? (
            <div className="inline-loading"><span className="spinner" /> Building your plan...</div>
          ) : studyPlan?.days_plan?.[0]?.tasks?.length ? (
            <>
              <div className="plan-overview">
                <div><span>Focus</span><b>{priorityTopic}</b></div>
                <div><span>Study time</span><b>{studyPlan.minutes_per_day ?? 60} min</b></div>
                <div><span>Accuracy</span><b>{priorityAccuracy == null ? "—" : `${priorityAccuracy}%`}</b></div>
              </div>
              {studyPlan.reason && <div className="insight"><b>AI insight</b><span>{studyPlan.reason}</span></div>}
              <div className="plan-list">
                {studyPlan.days_plan[0].tasks.map((task, index) => (
                  <PlanTask key={index} task={task} index={index} onClick={() => onQuiz(priorityTopic)} />
                ))}
              </div>
            </>
          ) : (
            <div className="empty-box">Complete a quiz to generate a personalized study path.</div>
          )}

          <button className="primary-button wide" onClick={onStartPlan} disabled={busy}>
            Start today's plan →
          </button>
        </div>

        <div className="white-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon blue">◫</span>
              <div>
                <h3>Continue learning</h3>
                <p>Your tracked topics</p>
              </div>
            </div>
            <button className="link-button" onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })}>View all</button>
          </div>

          <div className="topic-list">
            {topics.slice(0, 5).map((topic) => (
              <TopicCard key={topic.topic} topic={topic.topic} accuracy={topic.accuracy} onPractice={onQuiz} busy={busy} />
            ))}
            {!topics.length && <div className="empty-box">No topics yet. Take your first quiz to build your learning profile.</div>}
          </div>
        </div>
      </section>
    </div>
  );
}

function decisionText(decision) {
  if (!decision) return "";
  return decision.reason || `${decision.action || "Practice"} ${decision.topic || ""}`.trim();
}

function TutorView({
  question,
  setQuestion,
  answer,
  chatHistory,
  sourcePages,
  busy,
  onAsk,
  onClearChat,
  onQuiz,
  priorityTopic,
}) {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recognitionRef = React.useRef(null);

  const startVoiceInput = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      window.alert(
        "Voice input is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript;
      }
      setQuestion(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Voice input error:", event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const speakAnswer = (text) => {
    if (!text || !("speechSynthesis" in window)) {
      window.alert("Text-to-speech is not supported in this browser.");
      return;
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  return (
    <div className="page narrow-page">
      <section className="page-intro">
        <span className="section-kicker">AI TUTOR</span>
        <h1>Ask StudyAI anything.</h1>
        <p>Ask questions from your uploaded study material and get explanations in simple language.</p>
      </section>

      <div className="tutor-layout">
        <section className="chat-card">
          <div className="chat-toolbar">
            <div>
              <b>Study conversation</b>
              <span>{chatHistory.length ? `${Math.ceil(chatHistory.length / 2)} exchange${chatHistory.length > 2 ? "s" : ""}` : "New conversation"}</span>
            </div>
            {chatHistory.length > 0 && (
              <button className="ghost-button" onClick={onClearChat} type="button">Clear chat</button>
            )}
          </div>
          {chatHistory.length === 0 ? (
            <div className="empty-chat">
              <div className="big-ai-icon">✦</div>
              <h2>What are you learning today?</h2>
              <p>Ask for an explanation, summary, example, exam answer, or clarification.</p>
            </div>
          ) : (
            <div className="chat-history">
              {chatHistory.map((item, index) => (
                <div className={`chat-message ${item.role}`} key={index}>
                  <span className="message-role">{item.role === "user" ? "You" : "StudyAI"}</span>
                  <div className="message-content">
                    <div>{item.text}</div>
                    {item.role === "assistant" && (
                      <button
                        type="button"
                        className="message-speak-button"
                        onClick={() => speakAnswer(item.text)}
                        title={isSpeaking ? "Stop speaking" : "Read answer aloud"}
                      >
                        {isSpeaking ? "◼ Stop" : "🔊 Listen"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {sourcePages.length > 0 && (
            <div className="source-strip">
              <span>Sources from your PDF</span>
              <div>
                {sourcePages.map((page) => <span className="source-chip" key={page}>Page {page}</span>)}
              </div>
            </div>
          )}

          <form className="chat-composer" onSubmit={onAsk}>
            <div className="voice-composer">
              <button
                type="button"
                className={`voice-button ${isListening ? "voice-button-active" : ""}`}
                onClick={startVoiceInput}
                disabled={busy}
                title={isListening ? "Stop listening" : "Speak your question"}
              >
                <span className="voice-button-icon">{isListening ? "■" : "🎙️"}</span>
                <span>{isListening ? "Listening..." : "Speak"}</span>
              </button>
              <span className="voice-status">{isListening ? "I'm listening — ask your question" : "Voice input available"}</span>
            </div>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Type your question or tap Speak..."
              disabled={busy}
            />
            <div className="composer-bottom">
              <span>🎙️ Voice in · 🔊 Voice out · Powered by your RAG knowledge base</span>
              <button className="primary-button" disabled={busy || !question.trim()}>
                {busy ? "Thinking..." : "Ask StudyAI →"}
              </button>
            </div>
          </form>
        </section>

        <aside className="tutor-side">
          <div className="suggestion-card">
            <span className="section-kicker">TRY THIS</span>
            <button onClick={() => setQuestion(`Explain ${priorityTopic} in simple terms`)}>Explain {priorityTopic}<span>→</span></button>
            <button onClick={() => setQuestion(`Give me important exam points for ${priorityTopic}`)}>Exam points<span>→</span></button>
            <button onClick={() => onQuiz(priorityTopic)}>Quiz me on {priorityTopic}<span>→</span></button>
          </div>
          <div className="tip-card">
            <span>💡</span>
            <div><b>Study tip</b><p>Ask follow-up questions whenever an explanation is unclear. Your tutor is here to teach, not just answer.</p></div>
          </div>
        </aside>
      </div>

      {answer && chatHistory.length === 0 && (
        <div className="standalone-answer">
          <span className="section-kicker">STUDYAI</span>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );
}

function MaterialsView({ selectedFile, uploadStatus, uploadError, busy, onFileChange, onUpload, onAsk }) {
  return (
    <div className="page">
      <section className="page-intro">
        <span className="section-kicker">KNOWLEDGE BASE</span>
        <h1>Your study materials.</h1>
        <p>Upload PDFs and let StudyAI turn them into a searchable learning knowledge base.</p>
      </section>

      <section className="upload-hero">
        <div className="upload-hero-icon">↑</div>
        <div className="upload-copy">
          <span className="section-kicker">ADD MATERIAL</span>
          <h2>{selectedFile ? selectedFile.name : "Upload a study PDF"}</h2>
          <p>PDF files are chunked, embedded and connected to your AI tutor.</p>
          <div className="upload-actions">
            <label className="outline-button">
              Browse PDF
              <input id="pdf-upload-input" type="file" accept=".pdf,application/pdf" onChange={onFileChange} disabled={busy} />
            </label>
            <button className="primary-button" onClick={onUpload} disabled={busy || !selectedFile}>
              {busy ? "Processing..." : "Upload & process"}
            </button>
          </div>
        </div>
      </section>

      {uploadStatus && <div className="success-message">{uploadStatus}</div>}
      {uploadError && <div className="upload-error">{uploadError}</div>}

      <section className="material-info-grid">
        <div className="white-card info-card"><span>01</span><h3>Upload</h3><p>Select your lecture notes, textbook, or study PDF.</p></div>
        <div className="white-card info-card"><span>02</span><h3>Process</h3><p>StudyAI prepares the document for semantic search.</p></div>
        <div className="white-card info-card"><span>03</span><h3>Learn</h3><p>Ask questions, generate quizzes and build your study plan.</p></div>
      </section>

      <section className="cta-strip">
        <div><b>Ready to study?</b><span>Ask your AI tutor something about the material.</span></div>
        <button className="primary-button" onClick={onAsk}>Open AI Tutor →</button>
      </section>
    </div>
  );
}

function SmartNotesView({ topic, setTopic, result, busy, speaking, onGenerate, onSpeak, onStop, topics, onTopic }) {
  return (
    <div className="page">
      <section className="page-intro">
        <span className="section-kicker">SMART NOTES</span>
        <h1>Turn your study material into focused notes.</h1>
        <p>StudyAI searches your indexed material and creates concise, exam-ready notes for the topic you choose.</p>
      </section>

      <section className="smart-notes-layout">
        <div className="white-card smart-notes-control-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon blue">📝</span>
              <div><h3>Create smart notes</h3><p>Generated from your uploaded study material.</p></div>
            </div>
          </div>

          <label className="agent-label">TOPIC</label>
          <input
            className="agent-input"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Neural Networks"
          />

          <div className="smart-notes-topic-list">
            <span className="agent-label">QUICK TOPICS</span>
            <div className="smart-notes-chips">
              {topics.slice(0, 8).map((item) => (
                <button key={item.topic} className="smart-notes-chip" onClick={() => onTopic(item.topic)} disabled={busy}>
                  {item.topic}
                </button>
              ))}
            </div>
          </div>

          <button className="primary-button agent-run-button" onClick={() => onGenerate()} disabled={busy}>
            {busy ? "Generating notes..." : "Generate smart notes →"}
          </button>

          <div className="smart-notes-info">
            <strong>What you get</strong>
            <span>Definitions · key concepts · examples · applications · exam points</span>
          </div>
        </div>

        <div className="white-card smart-notes-result-card">
          <div className="card-heading">
            <div>
              <span className="mini-icon green">✓</span>
              <div><h3>{result?.topic || "Your notes"}</h3><p>{result ? "Generated from indexed study material." : "Choose a topic to create notes."}</p></div>
            </div>
          </div>

          {result ? (
            <>
              <div className="smart-notes-meta">
                <span>RAG grounded</span>
                {result.source_pages?.length ? <span>Pages: {result.source_pages.join(", ")}</span> : null}
              </div>
              <div className="smart-notes-output">{result.notes}</div>
              <div className="smart-notes-actions">
                <button className="agent-voice-button" onClick={onSpeak} disabled={speaking}>{speaking ? "🔊 Speaking..." : "🔊 Listen"}</button>
                <button className="agent-voice-button stop" onClick={onStop} disabled={!speaking}>⏹ Stop</button>
              </div>
            </>
          ) : (
            <div className="empty-box agent-empty">Your generated notes will appear here with the source pages used by the RAG system.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function QuizView({
  quizTopic,
  setQuizTopic,
  quiz,
  answers,
  setAnswers,
  quizResult,
  busy,
  onStart,
  onSubmit,
  onPractice,
  topics,
  priorityTopic,
}) {
  return (
    <div className="page">
      {!quiz && !quizResult && (
        <>
          <section className="page-intro">
            <span className="section-kicker">PRACTICE LAB</span>
            <h1>Test what you know.</h1>
            <p>StudyAI creates a short quiz from your learning material and uses the result to adapt your next steps.</p>
          </section>

          <section className="quiz-start-card">
            <div>
              <span className="big-ai-icon small">✓</span>
              <h2>Create a 5-question quiz</h2>
              <p>Choose a topic. Your stored performance can guide the difficulty.</p>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); onStart(); }}>
              <label>Topic</label>
              <input value={quizTopic} onChange={(e) => setQuizTopic(e.target.value)} placeholder="e.g. Pandas, CNN, DBMS..." disabled={busy} />
              <button className="primary-button wide" disabled={busy || !quizTopic.trim()}>
                {busy ? "Generating..." : "Generate quiz →"}
              </button>
            </form>
          </section>

          <div className="quick-topics">
            <span>Suggested topics</span>
            {topics.slice(0, 6).map((t) => (
              <button key={t.topic} onClick={() => onPractice(t.topic)} disabled={busy}>{t.topic}</button>
            ))}
            {priorityTopic !== "general" && <button className="recommended-chip" onClick={() => onPractice(priorityTopic)}>✦ {priorityTopic}</button>}
          </div>
        </>
      )}

      {quizResult && (
        <section className="result-card">
          <div className="result-circle">{quizResult.percentage ?? 0}%</div>
          <span className="section-kicker">QUIZ COMPLETE</span>
          <h1>{quizResult.score ?? 0} / {quizResult.total ?? 0}</h1>
          <p>{quizResult.recommendation || "Your learning profile has been updated."}</p>

          {quizResult.question_results?.length > 0 && (
            <div className="review-list">
              <div className="review-heading">
                <b>Review your answers</b>
                <span>{quizResult.question_results.filter((item) => item.is_correct).length} correct · {quizResult.question_results.filter((item) => !item.is_correct).length} to review</span>
              </div>

              {quizResult.question_results.map((item, index) => (
                <div className={`review-item ${item.is_correct ? "correct" : "incorrect"}`} key={index}>
                  <div className="review-status">{item.is_correct ? "✓" : "!"}</div>
                  <div className="review-content">
                    <strong>{index + 1}. {item.question}</strong>
                    <span>
                      Your answer: {item.selected_text || item.selected_answer || "Not answered"}
                    </span>
                    {!item.is_correct && (
                      <span className="review-correct">
                        Correct answer: {item.correct_text || item.correct_answer}
                      </span>
                    )}
                    {item.explanation && <p>{item.explanation}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="result-actions">
            {quizResult.next_decision?.topic && (
              <button className="primary-button" onClick={() => onPractice(quizResult.next_decision.topic)} disabled={busy}>
                Continue with {quizResult.next_decision.topic} →
              </button>
            )}
            <button className="secondary-button" onClick={() => onPractice(quizResult.topic || quizTopic)} disabled={busy}>
              Retry {quizResult.topic || quizTopic}
            </button>
          </div>
        </section>
      )}

      {quiz && (
        <section className="active-quiz" id="quiz-section">
          <div className="quiz-top">
            <div>
              <span className="section-kicker">ACTIVE QUIZ</span>
              <h1>{quiz.topic || quizTopic}</h1>
              <p>{(quiz.difficulty || "medium").toUpperCase()} · {quiz.questions?.length || 0} questions</p>
            </div>
            <span className="quiz-count">{answers.filter(Boolean).length}/{quiz.questions?.length || 0} answered</span>
          </div>

          <div className="quiz-progress">
            <div style={{ width: `${quiz.questions?.length ? (answers.filter(Boolean).length / quiz.questions.length) * 100 : 0}%` }} />
          </div>

          <div className="question-list">
            {quiz.questions?.map((q, i) => (
              <div className="question-card" key={i}>
                <div className="question-index">{String(i + 1).padStart(2, "0")}</div>
                <div className="question-body">
                  <h2>{q.question}</h2>
                  <div className="options-grid">
                    {getOptionEntries(q.options).map(([key, value]) => {
                      const optionText = String(value ?? "").replace(/^[A-Da-d]\s*[\)\.\:\-]\s*/, "").trim();
                      return (
                        <label className={`quiz-option ${answers[i] === key ? "selected" : ""}`} key={key}>
                          <input
                            type="radio"
                            name={`q-${i}`}
                            value={key}
                            checked={answers[i] === key}
                            onChange={() => {
                              const next = [...answers];
                              next[i] = key;
                              setAnswers(next);
                            }}
                            disabled={busy}
                          />
                          <span className="option-letter">{key}</span>
                          <span>{optionText}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button
            className="primary-button submit-button"
            onClick={onSubmit}
            disabled={busy || !quiz.questions?.length || answers.some((a) => !a)}
          >
            {busy ? "Evaluating..." : "Submit quiz & analyze →"}
          </button>
        </section>
      )}
    </div>
  );
}

function AgentToolsView({ action, setAction, question, setQuestion, topic, setTopic, result, busy, onExecute }) {
  const toolDescriptions = {
    auto: "Let StudyAI choose the appropriate learning tool from your request.",
    search: "Search the indexed study material and return the most relevant passages.",
    explain: "Retrieve study material and explain the selected topic clearly.",
    summarize: "Retrieve study material and create a focused summary.",
    exam: "Create an exam-ready answer using the indexed material.",
    quiz: "Generate an adaptive quiz for the selected topic.",
    plan: "Create a personalized study plan from your learning profile.",
    analyze: "Analyze performance, weak topics, strong topics, and recommendations.",
    next_action: "Ask the decision engine what the next learning action should be.",
  };

  const resultText = typeof result?.result === "string"
    ? result.result
    : result?.result
    ? JSON.stringify(result.result, null, 2)
    : "";

  const [isSpeaking, setIsSpeaking] = useState(false);

  function speakAgentResult() {
    if (!resultText) return;

    window.speechSynthesis.cancel();

    const text = String(resultText)
      .replace(/[{}[\]"]/g, "")
      .replace(/\\n/g, ". ")
      .replace(/,/g, ", ")
      .replace(/:/g, ": ");

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 0.92;
    utterance.pitch = 1;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  function stopAgentSpeech() {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }

  return (
    <div className="page">
      <section className="page-intro">
        <span className="section-kicker">AGENT TOOL CALLING</span>
        <h1>Let StudyAI choose and execute learning tools.</h1>
        <p>The agent can search your material, explain topics, generate quizzes, analyze progress, and create study plans.</p>
      </section>

      <section className="agent-tool-layout">
        <div className="white-card agent-control-card">
          <div className="card-heading">
            <div><span className="mini-icon blue">⚡</span><div><h3>Tool selector</h3><p>Choose a tool or let the agent decide.</p></div></div>
          </div>
          <label className="agent-label">ACTION</label>
          <select className="agent-select" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="auto">Auto — decide for me</option>
            <option value="search">Search Documents</option>
            <option value="explain">Explain Topic</option>
            <option value="summarize">Summarize Topic</option>
            <option value="exam">Exam Answer</option>
            <option value="quiz">Generate Quiz</option>
            <option value="plan">Create Study Plan</option>
            <option value="analyze">Analyze Performance</option>
            <option value="next_action">Choose Next Action</option>
          </select>

          <label className="agent-label">TOPIC</label>
          <input className="agent-input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Java Collections" />

          <label className="agent-label">QUESTION / REQUEST</label>
          <textarea className="agent-textarea" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Explain HashMap with an example" />

          <div className="agent-description">{toolDescriptions[action]}</div>
          <button className="primary-button agent-run-button" onClick={onExecute} disabled={busy}>
            {busy ? "Agent working..." : "Run agent tool →"}
          </button>
        </div>

        <div className="white-card agent-result-card">
          <div className="card-heading">
            <div><span className="mini-icon green">✓</span><div><h3>Execution result</h3><p>{result ? `Tool: ${result.tool}` : "Your agent output will appear here."}</p></div></div>
          </div>
          {result ? (
            <>
              <div className="agent-result-meta">
                <span>{result.status || "completed"}</span>
                {result.topic && <span>Topic: {result.topic}</span>}
              </div>
              <pre className="agent-result-output">{resultText}</pre>
              <div className="agent-result-actions">
                {!isSpeaking ? (
                  <button
                    type="button"
                    className="agent-voice-button"
                    onClick={speakAgentResult}
                    disabled={!resultText}
                  >
                    🔊 Listen
                  </button>
                ) : (
                  <button
                    type="button"
                    className="agent-voice-button stop"
                    onClick={stopAgentSpeech}
                  >
                    ⏹ Stop
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="empty-box agent-empty">Choose a tool and run it to see the agent's decision and output.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function ProgressView({
  student,
  topics,
  strongTopics,
  weakTopics,
  analytics,
  recentQuizzes,
  onPractice,
  busy,
}) {
  return (
    <div className="page">
      <section className="page-intro">
        <span className="section-kicker">LEARNING ANALYTICS</span>
        <h1>See how you're progressing.</h1>
        <p>StudyAI tracks quiz performance and turns it into useful practice recommendations.</p>
      </section>

      <section className="progress-hero">
        <div className="progress-score">
          <span>OVERALL ACCURACY</span>
          <strong>{student.accuracy ?? 0}%</strong>
          <ProgressBar value={student.accuracy ?? 0} />
        </div>
        <div className="progress-stat"><b>{student.total_quizzes ?? 0}</b><span>Quizzes</span></div>
        <div className="progress-stat"><b>{student.total_questions ?? 0}</b><span>Questions</span></div>
        <div className="progress-stat"><b>{topics.length}</b><span>Topics</span></div>
      </section>

      <section className="two-column">
        <div className="white-card">
          <div className="card-heading"><div><span className="mini-icon green">↑</span><div><h3>Strong topics</h3><p>Areas where you're performing well</p></div></div></div>
          {strongTopics.length ? strongTopics.map((t) => <TopicCard key={t.topic} topic={t.topic} accuracy={t.accuracy} onPractice={onPractice} busy={busy} />) : <div className="empty-box">No strong topics yet.</div>}
        </div>

        <div className="white-card">
          <div className="card-heading"><div><span className="mini-icon red">↓</span><div><h3>Topics to improve</h3><p>Areas that need more practice</p></div></div></div>
          {weakTopics.length ? weakTopics.map((t) => <TopicCard key={t.topic} topic={t.topic} accuracy={t.accuracy} onPractice={onPractice} busy={busy} />) : <div className="empty-box">No weak topics detected yet.</div>}
        </div>
      </section>

      <section className="white-card">
        <div className="card-heading"><div><span className="mini-icon blue">◫</span><div><h3>All tracked topics</h3><p>Your current performance by topic</p></div></div></div>
        <div className="topics-grid">
          {topics.map((t) => <TopicCard key={t.topic} topic={t.topic} accuracy={t.accuracy} onPractice={onPractice} busy={busy} />)}
          {!topics.length && <div className="empty-box">Complete a quiz to start tracking topics.</div>}
        </div>
      </section>
    </div>
  );
}

export default App;
