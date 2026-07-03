import React, { useEffect, useRef } from "react";
import Message from "./Message";
import ChatInput from "./ChatInput";
import { Sparkles, HelpCircle, FileText, Activity } from "lucide-react";

export default function ChatWindow({ messages, isLoading, onSendMessage }) {
  const bottomRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const suggestions = [
    {
      title: "Analyze Symptoms",
      desc: "What are common signs of cardiovascular issues?",
      prompt: "What are the primary symptoms and risk factors associated with cardiovascular diseases?"
    },
    {
      title: "Explain Medication",
      desc: "How does Metformin work for diabetes?",
      prompt: "Can you explain the mechanism of action, common dosage, and side effects of Metformin for managing diabetes?"
    },
    {
      title: "Query Knowledge Base",
      desc: "Search central medical libraries and papers",
      prompt: "Summarize the primary medical studies or guidelines currently active in the RAG knowledge base."
    }
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-900 overflow-hidden relative">
      {/* Top Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-clinical-500 animate-pulse" />
          <div>
            <h1 className="text-sm font-semibold text-slate-100">Consultation Session</h1>
            <p className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
              Secured MedAI Agent Online
            </p>
          </div>
        </div>
      </div>

      {/* Message List Area */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-4">
        {messages.length === 0 ? (
          /* Welcome Screen */
          <div className="max-w-2xl mx-auto py-12 flex flex-col items-center justify-center text-center h-full">
            <div className="w-14 h-14 rounded-2xl bg-clinical-500/10 border border-clinical-500/20 flex items-center justify-center text-clinical-400 mb-6 shadow-lg shadow-clinical-500/5">
              <Activity className="w-7 h-7" />
            </div>
            
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Welcome to <span className="text-transparent bg-clip-text bg-gradient-to-r from-clinical-400 to-indigo-400">MedAI</span>
            </h2>
            <p className="mt-2 text-sm sm:text-base text-slate-400 max-w-md">
              Your intelligent clinical assistant. Ask medical questions to query pre-ingested health guidelines with semantic context retrieval.
            </p>

            {/* Recommendations Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full mt-10">
              {suggestions.map((sug, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(sug.prompt)}
                  className="flex flex-col items-start p-4 rounded-xl bg-slate-800/40 border border-slate-800 hover:border-clinical-500/30 hover:bg-clinical-950/10 text-left transition-all duration-300 group"
                >
                  <div className="bg-slate-800 p-1.5 rounded-lg text-clinical-400 mb-3 group-hover:bg-clinical-500/10 group-hover:text-clinical-400 transition-colors">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <h3 className="text-xs font-semibold text-slate-200 group-hover:text-clinical-400 transition-colors">
                    {sug.title}
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                    {sug.desc}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Chat List */
          <div className="max-w-4xl mx-auto w-full">
            {messages.map((msg, idx) => (
              <Message key={idx} message={msg} />
            ))}

            {/* Typing Indicator */}
            {isLoading && (
              <div className="flex w-full gap-4 py-6 border-b border-slate-800/40 justify-start">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-clinical-600 flex items-center justify-center text-white shadow-md shadow-clinical-500/10">
                  <Activity className="w-5 h-5" />
                </div>
                <div className="flex flex-col gap-2 items-start">
                  <span className="text-xs font-semibold text-slate-400 px-1">
                    MedAI Assistant
                  </span>
                  <div className="rounded-2xl px-4 py-3 bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-tl-none flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-clinical-400 animate-bounce [animation-delay:-0.3s]"></span>
                    <span className="w-2 h-2 rounded-full bg-clinical-400 animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-2 h-2 rounded-full bg-clinical-400 animate-bounce"></span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 p-4 sm:p-6 bg-slate-900 border-t border-slate-800/80">
        <ChatInput onSendMessage={onSendMessage} isLoading={isLoading} />
        <p className="text-[10px] text-slate-500 text-center mt-3">
          MedAI can make mistakes. Please verify clinical information with qualified professionals.
        </p>
      </div>
    </div>
  );
}
