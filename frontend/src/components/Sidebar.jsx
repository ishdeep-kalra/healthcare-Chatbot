import React from "react";
import { MessageSquare, Plus, Trash2, Activity, ShieldCheck, History } from "lucide-react";

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onNewChat,
}) {
  return (
    <div className="w-[280px] h-full bg-slate-950 border-r border-slate-800 flex flex-col flex-shrink-0">
      {/* Header Logo */}
      <div className="p-5 flex items-center justify-between border-b border-slate-900 bg-slate-950">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-clinical-500 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-clinical-500/10">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <span className="text-base font-extrabold text-white tracking-wide">MedAI</span>
            <div className="text-[9px] text-clinical-400 font-bold tracking-wider uppercase leading-none mt-0.5">
              RAG Engine v1.0
            </div>
          </div>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="p-4 flex flex-col gap-4 border-b border-slate-900 bg-slate-950/40">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-clinical-600 hover:bg-clinical-500 text-white font-semibold text-sm shadow-md shadow-clinical-600/10 transition-all duration-200 active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          New Consultation
        </button>
      </div>

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-wider px-2 mb-2">
          <History className="w-3.5 h-3.5" />
          Recent Consultations
        </div>

        {sessions.length === 0 ? (
          <div className="text-center py-8 px-4 text-xs text-slate-500">
            No previous sessions. Start typing to save history.
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              return (
                <div
                  key={session.id}
                  onClick={() => onSelectSession(session.id)}
                  className={`group flex items-center justify-between w-full p-2.5 rounded-xl text-left cursor-pointer transition-all duration-200 ${
                    isActive
                      ? "bg-slate-800 text-white font-medium border border-slate-700/50"
                      : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-clinical-400" : "text-slate-500"}`} />
                    <span className="text-xs truncate pr-1">
                      {session.name || "New Consultation"}
                    </span>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    className={`p-1.5 rounded-md text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all ${
                      isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                    }`}
                    title="Delete Session"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-900 bg-slate-950 flex items-center gap-2 text-slate-400 text-xs">
        <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
        <span className="truncate">Compliance Guardrails Active</span>
      </div>
    </div>
  );
}
