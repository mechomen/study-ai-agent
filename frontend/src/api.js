import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// ==========================================
// AUTH TOKEN
// ==========================================

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("studyai_token");

  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// ==========================================
// AUTH ERROR HANDLING
// ==========================================

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("studyai_token");
      localStorage.removeItem("studyai_user");
    }

    return Promise.reject(error);
  }
);

// ==========================================
// AUTHENTICATION
// ==========================================

export const loginUser = async (email, password) => {
  const response = await api.post("/api/auth/login", {
    email,
    password,
  });

  return response.data;
};

export const registerUser = async (name, email, password) => {
  const response = await api.post("/api/auth/register", {
    name,
    email,
    password,
  });

  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get("/api/auth/me");

  return response.data;
};

export const logoutUser = async () => {
  const response = await api.post("/api/auth/logout");

  return response.data;
};

// ==========================================
// DASHBOARD
// ==========================================

export const getDashboard = async () => {
  const response = await api.get("/api/dashboard");

  return response.data;
};

// ==========================================
// MEMORY
// ==========================================

export const getMemory = async () => {
  const response = await api.get("/api/memory");

  return response.data;
};

// ==========================================
// DECISION
// ==========================================

export const getDecision = async () => {
  const response = await api.get("/api/decision");

  return response.data;
};

// ==========================================
// RECOMMENDATION
// ==========================================

export const getRecommendation = async () => {
  const response = await api.get("/api/recommendation");

  return response.data;
};

// ==========================================
// ASK STUDY AI
// ==========================================

export const askQuestion = async (question, history = []) => {
  const response = await api.post("/api/ask", {
    question,
    history,
  });

  return response.data;
};

// ==========================================
// SMART NOTES
// ==========================================

export const generateSmartNotes = async (topic) => {
  const response = await api.post("/api/smart-notes", {
    topic,
  });

  return response.data;
};

// ==========================================
// QUIZ
// ==========================================

export const createQuiz = async (topic, count = 5) => {
  const response = await api.post("/api/quiz", {
    topic,
    count,
  });

  return response.data;
};

export const startQuiz = async (topic, numQuestions = 5) => {
  const response = await api.post("/api/quiz", {
    topic,
    count: numQuestions,
  });

  return response.data;
};

// ==========================================
// SUBMIT QUIZ
// ==========================================

export const submitQuiz = async (quizId, answers) => {
  const response = await api.post("/api/quiz/submit", {
    quiz_id: quizId,
    answers,
  });

  return response.data;
};

// ==========================================
// STUDY PLAN
// ==========================================

export const getStudyPlan = async (
  days = 1,
  minutesPerDay = 60
) => {
  const response = await api.get("/api/study-plan", {
    params: {
      days,
      minutes_per_day: minutesPerDay,
    },
  });

  return response.data;
};

export const createStudyPlan = async (
  days = 1,
  minutesPerDay = 60
) => {
  const response = await api.post("/api/study-plan", null, {
    params: {
      days,
      minutes_per_day: minutesPerDay,
    },
  });

  return response.data;
};

// ==========================================
// STUDY SESSION
// ==========================================

export const startStudySession = async () => {
  const response = await api.post("/api/study-session");

  return response.data;
};

// ==========================================
// AUTONOMOUS SESSION
// ==========================================

export const startAutonomousSession = async () => {
  const response = await api.post("/api/autonomous-session");

  return response.data;
};

// ==========================================
// AGENT TOOL CALLING
// ==========================================

export const executeAgentAction = async (payload) => {
  const response = await api.post(
    "/api/agent/execute",
    payload
  );

  return response.data;
};

// ==========================================
// PDF UPLOAD
// ==========================================

export const uploadPdf = async (file) => {
  const formData = new FormData();

  formData.append("file", file);

  const response = await api.post(
    "/api/upload-pdf",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
};

// ==========================================
// DEFAULT EXPORT
// ==========================================

export default api;