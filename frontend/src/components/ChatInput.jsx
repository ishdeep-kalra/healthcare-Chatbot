import React, { useState, useRef, useEffect } from "react";
import { Send, ArrowUp } from "lucide-react";

export default function ChatInput({ onSendMessage, isLoading, placeholder }) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  // Auto-resize textarea to fit text
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text.trim());
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter, unless Shift is pressed
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="relative flex items-end w-full max-w-4xl mx-auto rounded-2xl border border-slate-700/65 bg-slate-800/90 shadow-lg transition-all focus-within:border-clinical-500 focus-within:ring-2 focus-within:ring-clinical-500/20 px-3 py-2.5 gap-2"
    >
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || "Ask a healthcare question..."}
        disabled={isLoading}
        className="flex-1 max-h-[200px] min-h-[24px] resize-none bg-transparent outline-none border-0 text-slate-100 placeholder-slate-400 text-sm sm:text-base pr-10 pl-2 py-1.5 focus:ring-0 focus:outline-none"
      />

      <button
        type="submit"
        disabled={!text.trim() || isLoading}
        className={`flex-shrink-0 flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-xl transition-all duration-200 ${
          text.trim() && !isLoading
            ? "bg-clinical-600 hover:bg-clinical-500 text-white cursor-pointer active:scale-95"
            : "bg-slate-700/40 text-slate-500 cursor-not-allowed"
        }`}
      >
        <Send className="w-4 h-4 sm:w-5 h-5" />
      </button>
    </form>
  );
}
