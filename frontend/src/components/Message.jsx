import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { User, Activity, BookOpen, ChevronDown, ChevronUp, FileText } from "lucide-react";

export default function Message({ message }) {
  const { sender, text, sources } = message;
  const isUser = sender === "user";
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  // Helper to format relevance score
  const formatScore = (score) => {
    if (score == null) return null;
    // Handle both 0-1 range and 0-100 range
    const val = score <= 1 ? score * 100 : score;
    return `${Math.round(val)}%`;
  };

  // Helper to get score color class
  const getScoreColor = (score) => {
    if (score == null) return "bg-slate-700 text-slate-300";
    const val = score <= 1 ? score * 100 : score;
    if (val >= 80) return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    if (val >= 50) return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    return "bg-rose-500/10 text-rose-400 border-rose-500/20";
  };

  return (
    <div className={`flex w-full gap-4 py-6 border-b border-slate-800/40 first-of-type:pt-2 last-of-type:border-0 ${
      isUser ? "justify-end" : "justify-start"
    }`}>
      {/* Bot Avatar (Left side) */}
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-clinical-600 flex items-center justify-center text-white shadow-md shadow-clinical-500/10 animate-fade-in">
          <Activity className="w-5 h-5" />
        </div>
      )}

      {/* Bubble Content */}
      <div className={`flex flex-col max-w-[85%] sm:max-w-[75%] gap-2 ${isUser ? "items-end" : "items-start"}`}>
        {/* Header Sender Info */}
        <span className="text-xs font-semibold text-slate-400 px-1">
          {isUser ? "You" : "MedAI Assistant"}
        </span>

        {/* Message Bubble */}
        <div className={`rounded-2xl px-4 py-3.5 shadow-sm text-sm sm:text-base leading-relaxed break-words ${
          isUser
            ? "bg-gradient-to-br from-clinical-600 to-clinical-700 text-white rounded-tr-none"
            : "bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-tl-none"
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{text}</p>
          ) : (
            <ReactMarkdown
              components={{
                p: ({ node, ...props }) => <p className="mb-3 last:mb-0 text-slate-200" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-3 space-y-1.5 text-slate-200" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-3 space-y-1.5 text-slate-200" {...props} />,
                li: ({ node, ...props }) => <li className="pl-0.5" {...props} />,
                h1: ({ node, ...props }) => <h1 className="text-lg font-bold text-white mt-4 mb-2 first:mt-0" {...props} />,
                h2: ({ node, ...props }) => <h2 className="text-md font-semibold text-white mt-3.5 mb-2 first:mt-0" {...props} />,
                h3: ({ node, ...props }) => <h3 className="text-sm font-semibold text-white mt-3 mb-1 first:mt-0" {...props} />,
                strong: ({ node, ...props }) => <strong className="font-semibold text-clinical-400" {...props} />,
                code: ({ node, inline, ...props }) => (
                  <code className={`${
                    inline 
                      ? "bg-slate-900/60 text-clinical-400 px-1.5 py-0.5 rounded text-xs font-mono" 
                      : "block bg-slate-900/60 text-slate-300 p-3 rounded-lg text-xs font-mono overflow-x-auto my-3 border border-slate-700/40"
                  }`} {...props} />
                ),
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-4 rounded-lg border border-slate-700/50">
                    <table className="min-w-full divide-y divide-slate-700 text-left text-xs sm:text-sm" {...props} />
                  </div>
                ),
                th: ({ node, ...props }) => <th className="bg-slate-900/60 px-4 py-2.5 font-semibold text-slate-200 border-b border-slate-700" {...props} />,
                td: ({ node, ...props }) => <td className="px-4 py-2 text-slate-300 border-b border-slate-800 last:border-0" {...props} />,
              }}
            >
              {text}
            </ReactMarkdown>
          )}
        </div>

        {/* Sources Accordion */}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2 w-full">
            <button
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-slate-400 hover:text-clinical-400 hover:bg-slate-800/60 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>
                {sourcesExpanded ? "Hide Sources" : `View Sources (${sources.length})`}
              </span>
              {sourcesExpanded ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>

            {sourcesExpanded && (
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full animate-fade-in">
                {sources.map((src, idx) => (
                  <div
                    key={idx}
                    className="flex flex-col p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50 hover:border-slate-600/50 transition-colors gap-1.5"
                  >
                    <div className="flex items-start gap-1.5">
                      <FileText className="w-4 h-4 text-clinical-500 mt-0.5 flex-shrink-0" />
                      <span className="text-xs font-medium text-slate-300 truncate flex-1" title={src.source}>
                        {src.source}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[10px] text-slate-400 font-medium">
                      <span className="bg-slate-700/50 px-1.5 py-0.5 rounded border border-slate-700">
                        Page {src.page}
                      </span>
                      {src.relevance_score != null && (
                        <span className={`px-1.5 py-0.5 rounded border ${getScoreColor(src.relevance_score)}`}>
                          Relevance: {formatScore(src.relevance_score)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* User Avatar (Right side) */}
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center text-slate-200 shadow-md">
          <User className="w-5 h-5" />
        </div>
      )}
    </div>
  );
}
