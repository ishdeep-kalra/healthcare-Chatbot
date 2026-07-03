import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { CheckCircle, AlertTriangle, X } from "lucide-react";
import axios from "axios";

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Toast Helper
  const addToast = (message, type = "success") => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, message, type }]);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Load sessions from local storage on mount
  useEffect(() => {
    const storedSessions = localStorage.getItem("medai_sessions");
    const storedActiveId = localStorage.getItem("medai_active_session_id");

    if (storedSessions) {
      const parsed = JSON.parse(storedSessions);
      setSessions(parsed);
      if (storedActiveId && parsed.some(s => s.id === storedActiveId)) {
        setActiveSessionId(storedActiveId);
      } else if (parsed.length > 0) {
        setActiveSessionId(parsed[0].id);
      } else {
        createNewSession();
      }
    } else {
      createNewSession();
    }
  }, []);

  // Save sessions to local storage on change
  const saveSessions = (updatedSessions, newActiveId = null) => {
    setSessions(updatedSessions);
    localStorage.setItem("medai_sessions", JSON.stringify(updatedSessions));
    
    if (newActiveId) {
      setActiveSessionId(newActiveId);
      localStorage.setItem("medai_active_session_id", newActiveId);
    } else if (activeSessionId) {
      localStorage.setItem("medai_active_session_id", activeSessionId);
    }
  };

  // Create a new empty session
  const createNewSession = () => {
    const newSession = {
      id: Date.now().toString(),
      name: "New Consultation",
      messages: [],
    };
    
    // Read current sessions list, append new one
    let currentSessions = [];
    const stored = localStorage.getItem("medai_sessions");
    if (stored) {
      try {
        currentSessions = JSON.parse(stored);
      } catch (e) {
        console.error("Failed to parse sessions during creation", e);
      }
    }

    const updated = [newSession, ...currentSessions];
    saveSessions(updated, newSession.id);
  };

  // Delete a session
  const handleDeleteSession = (id) => {
    const updated = sessions.filter((s) => s.id !== id);
    let nextActiveId = activeSessionId;

    if (activeSessionId === id) {
      nextActiveId = updated.length > 0 ? updated[0].id : null;
    }

    saveSessions(updated, nextActiveId);
    addToast("Session deleted successfully", "success");

    // If no sessions remain, auto-create one
    if (updated.length === 0) {
      const newSession = {
        id: Date.now().toString(),
        name: "New Consultation",
        messages: [],
      };
      saveSessions([newSession], newSession.id);
    }
  };

  // Switch to another session
  const handleSelectSession = (id) => {
    setActiveSessionId(id);
    localStorage.setItem("medai_active_session_id", id);
  };

  // Send Chat message to FastAPI Backend
  const handleSendMessage = async (text) => {
    if (!text.trim() || isLoading || !activeSessionId) return;

    // Get current active session
    const currentSessionIndex = sessions.findIndex((s) => s.id === activeSessionId);
    if (currentSessionIndex === -1) return;

    const currentSession = sessions[currentSessionIndex];
    const userMessage = { sender: "user", text };
    
    // Update session name if it was the first message
    let updatedName = currentSession.name;
    if (currentSession.messages.length === 0) {
      updatedName = text.length > 30 ? `${text.slice(0, 30)}...` : text;
    }

    const updatedMessages = [...currentSession.messages, userMessage];
    
    // Update temporary state
    const updatedSessions = sessions.map((s) =>
      s.id === activeSessionId
        ? { ...s, name: updatedName, messages: updatedMessages }
        : s
    );
    saveSessions(updatedSessions);

    // Call API backend
    setIsLoading(true);
    try {
      const response = await axios.post("http://127.0.0.1:8000/api/chat", {
        question: text,
      });

      if (response.data.status === "success" || response.status === 200) {
        const botMessage = {
          sender: "ai",
          text: response.data.answer || "I could not retrieve an answer.",
          sources: response.data.sources || [],
        };

        const finalSessions = sessions.map((s) =>
          s.id === activeSessionId
            ? { ...s, name: updatedName, messages: [...updatedMessages, botMessage] }
            : s
        );
        saveSessions(finalSessions);
      } else {
        throw new Error(response.data.message || "Invalid answer structure received.");
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorMsg = error.response?.data?.detail || error.message || "Failed to communicate with API server.";
      
      const errorBotMessage = {
        sender: "ai",
        text: `❌ **Failed to retrieve answer.**\n\nError details: *${errorMsg}*\n\nPlease make sure the FastAPI backend is running at \`http://localhost:8000\` and try again.`,
        sources: [],
      };

      const finalSessions = sessions.map((s) =>
        s.id === activeSessionId
          ? { ...s, name: updatedName, messages: [...updatedMessages, errorBotMessage] }
          : s
      );
      saveSessions(finalSessions);
      addToast(errorMsg, "error");
    } finally {
      setIsLoading(false);
    }
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId) || {
    messages: [],
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-900 text-slate-100 font-sans">
      {/* Toast Notification Layer */}
      <div className="fixed top-6 right-6 z-50 flex flex-col gap-2.5 max-w-md w-full sm:w-auto">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-start gap-3 p-4 rounded-xl border shadow-lg backdrop-blur-md animate-fade-in transition-all duration-300 ${
              toast.type === "success"
                ? "bg-slate-950/90 border-emerald-500/30 text-slate-200"
                : "bg-slate-950/90 border-rose-500/30 text-slate-200"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-400 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1 flex flex-col gap-0.5 pr-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {toast.type === "success" ? "Notification" : "Error Alert"}
              </span>
              <p className="text-xs text-slate-300 font-medium leading-relaxed">{toast.message}</p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-slate-500 hover:text-slate-200 p-0.5 rounded-lg hover:bg-slate-800/50 transition-colors flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Main Layout */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onNewChat={createNewSession}
      />

      <ChatWindow
        messages={activeSession.messages}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
      />
    </div>
  );
}