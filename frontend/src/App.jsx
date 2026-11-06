import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { CheckCircle, AlertTriangle, X } from "lucide-react";
import { API_ENDPOINTS, API_BASE_URL } from "./api/config";

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

    // Immediately insert user message and a placeholder AI message with live status Updates
    const botPlaceholderMessage = {
      sender: "ai",
      text: "",
      sources: [],
      statusUpdates: ["🔍 Searching uploaded medical documents..."],
      model: "",
      isStreaming: true,
    };
    const updatedMessages = [...currentSession.messages, userMessage, botPlaceholderMessage];
    
    const updatedSessions = sessions.map((s) =>
      s.id === activeSessionId
        ? { ...s, name: updatedName, messages: updatedMessages }
        : s
    );
    saveSessions(updatedSessions);
    setIsLoading(true);

    try {
      const response = await fetch(API_ENDPOINTS.chat, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text,
          stream: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to communicate with API server.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = "";

      let accumulatedText = "";
      let statusUpdates = ["🔍 Searching uploaded medical documents..."];
      let model = "";
      let sources = [];

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: !done });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let stateChanged = false;

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            if (trimmed.startsWith("data: ")) {
              const dataStr = trimmed.slice(6);
              try {
                const data = JSON.parse(dataStr);
                if (data.type === "status") {
                  if (!statusUpdates.includes(data.message)) {
                    statusUpdates = [...statusUpdates, data.message];
                    stateChanged = true;
                  }
                } else if (data.type === "model") {
                  model = data.name;
                  stateChanged = true;
                } else if (data.type === "sources") {
                  sources = data.sources;
                  stateChanged = true;
                } else if (data.type === "token") {
                  accumulatedText += data.content;
                  stateChanged = true;
                } else if (data.type === "error") {
                  throw new Error(data.message);
                }
              } catch (e) {
                console.error("Error parsing stream line:", line, e);
              }
            }
          }

          if (stateChanged) {
            setSessions((prevSessions) =>
              prevSessions.map((s) => {
                if (s.id === activeSessionId) {
                  const messagesCopy = [...s.messages];
                  const lastMsg = { ...messagesCopy[messagesCopy.length - 1] };
                  lastMsg.text = accumulatedText;
                  lastMsg.statusUpdates = statusUpdates;
                  lastMsg.model = model;
                  lastMsg.sources = sources;
                  lastMsg.isStreaming = !done;
                  messagesCopy[messagesCopy.length - 1] = lastMsg;
                  return { ...s, messages: messagesCopy };
                }
                return s;
              })
            );
          }
        }
      }

      // Persist final state to localstorage
      setSessions((prevSessions) => {
        const final = prevSessions.map((s) => {
          if (s.id === activeSessionId) {
            const messagesCopy = [...s.messages];
            const lastMsg = { ...messagesCopy[messagesCopy.length - 1] };
            lastMsg.text = accumulatedText;
            lastMsg.statusUpdates = statusUpdates;
            lastMsg.model = model;
            lastMsg.sources = sources;
            lastMsg.isStreaming = false;
            messagesCopy[messagesCopy.length - 1] = lastMsg;
            return { ...s, messages: messagesCopy };
          }
          return s;
        });
        localStorage.setItem("medai_sessions", JSON.stringify(final));
        return final;
      });

    } catch (error) {
      console.error("Chat error:", error);
      const errorMsg = error.message || "Failed to communicate with API server.";
      
      const errorBotMessage = {
        sender: "ai",
        text: `❌ **Failed to retrieve answer.**\n\nError details: *${errorMsg}*\n\nPlease try again. If the problem persists, the backend service may be temporarily unavailable.`,
        sources: [],
        statusUpdates: [],
        model: "",
        isStreaming: false,
      };

      setSessions((prevSessions) => {
        const final = prevSessions.map((s) => {
          if (s.id === activeSessionId) {
            const messagesCopy = [...s.messages];
            messagesCopy[messagesCopy.length - 1] = errorBotMessage;
            return { ...s, name: updatedName, messages: messagesCopy };
          }
          return s;
        });
        localStorage.setItem("medai_sessions", JSON.stringify(final));
        return final;
      });

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