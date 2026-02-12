"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import HandoffBanner from "./HandoffBanner";
import SuggestionChips from "./SuggestionChips";
import LanguageToggle from "./LanguageToggle";

interface Source {
  url: string;
  title: string;
}

interface HandoffInfo {
  email: string;
  phone: string;
  url: string;
  summary?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  id?: number;
  confidence?: number;
  lowConfidence?: boolean;
  handoff?: HandoffInfo | null;
  feedbackGiven?: 1 | -1 | null;
}

interface Suggestion {
  text: string;
  query: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChatWidget() {
  const { lang, t } = useLanguage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [handoffInfo, setHandoffInfo] = useState<HandoffInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Initialize session and load history
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const storedSession = localStorage.getItem("vernon-session-id");

    if (storedSession) {
      setSessionId(storedSession);
      // Load conversation history
      fetch(`${API_URL}/api/sessions/${storedSession}/messages`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.messages?.length > 0) {
            setMessages(
              data.messages.map((m: any) => ({
                role: m.role,
                content: m.content,
                sources: m.sources,
                id: m.id,
                confidence: m.confidence,
              }))
            );
            setShowSuggestions(false);
          } else {
            setMessages([{ role: "assistant", content: t("greeting") }]);
          }
        })
        .catch(() => {
          setMessages([{ role: "assistant", content: t("greeting") }]);
        });
    } else {
      setMessages([{ role: "assistant", content: t("greeting") }]);
    }
  }, [t]);

  // Load suggestions
  useEffect(() => {
    fetch(`${API_URL}/api/suggestions?language=${lang}`)
      .then((r) => r.json())
      .then(setSuggestions)
      .catch(() => {});
  }, [lang]);

  const handleFeedback = async (messageId: number, rating: 1 | -1) => {
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: messageId, rating }),
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedbackGiven: rating } : m))
      );
    } catch {
      // Silently fail on feedback
    }
  };

  const sendMessage = async (content: string) => {
    setShowSuggestions(false);
    setHandoffInfo(null);

    const userMessage: Message = { role: "user", content };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    const assistantMessage: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          stream: true,
          session_id: sessionId,
          language: lang,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to get response");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";
      let sources: Source[] = [];
      let msgId: number | undefined;
      let confidence: number | undefined;
      let handoff: HandoffInfo | null = null;
      let newSessionId: string | undefined;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.token) {
                  accumulatedText += data.token;
                  setMessages((prev) => {
                    const updated = [...prev];
                    updated[updated.length - 1] = {
                      role: "assistant",
                      content: accumulatedText,
                    };
                    return updated;
                  });
                }
                if (data.sources) sources = data.sources;
                if (data.confidence !== undefined) confidence = data.confidence;
                if (data.message_id) msgId = data.message_id;
                if (data.session_id) newSessionId = data.session_id;
                if (data.email !== undefined || data.phone !== undefined || data.url !== undefined) {
                  handoff = { email: data.email || "", phone: data.phone || "", url: data.url || "", summary: data.summary || "" };
                }
              } catch {
                // Skip malformed lines
              }
            }
          }
        }
      }

      // Store session
      if (newSessionId) {
        setSessionId(newSessionId);
        localStorage.setItem("vernon-session-id", newSessionId);
      }

      if (handoff && (handoff.email || handoff.phone || handoff.url)) {
        setHandoffInfo(handoff);
      }

      // Strip confidence/handoff markers that may have leaked into visible text
      let cleanText = accumulatedText;
      cleanText = cleanText.replace(/\[CONFIDENCE:[\d.]+\]/g, "").trim();
      cleanText = cleanText.replace(/\[HANDOFF_NEEDED\]/g, "").trim();

      const isLowConf = confidence !== undefined && confidence < 0.65;

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: cleanText || "Sorry, I couldn't generate a response.",
          sources: sources.length > 0 ? sources : undefined,
          id: msgId,
          confidence,
          lowConfidence: isLowConf,
          handoff,
        };
        return updated;
      });
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content:
            error instanceof Error
              ? `Error: ${error.message}`
              : t("errorGeneric"),
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      id="chat-main"
      className="bg-white rounded-2xl shadow-lg border border-gray-200 flex flex-col h-[600px]"
      role="region"
      aria-label={t("title")}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-blue-600 to-blue-700 rounded-t-2xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse" aria-hidden="true" />
            <h2 className="text-white font-semibold">{t("title")}</h2>
          </div>
          <div className="flex items-center gap-3">
            <LanguageToggle />
            <button
              onClick={() =>
                setHandoffInfo({
                  email: "",
                  phone: "",
                  url: "https://www.vernon.ca/contact-us",
                })
              }
              className="text-xs text-white/80 hover:text-white underline transition-colors"
              aria-label={t("talkToPerson")}
            >
              {t("talkToPerson")}
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-4 chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg, i) => (
          <MessageBubble
            key={`${i}-${msg.id || ""}`}
            message={msg}
            onFeedback={handleFeedback}
          />
        ))}
        {isLoading && messages[messages.length - 1]?.content === "" && (
          <div className="flex items-center gap-2 text-gray-400 text-sm pl-2" aria-live="assertive">
            <div className="flex gap-1" aria-hidden="true">
              <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" />
              <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
              <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
            </div>
            {t("thinking")}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Handoff banner */}
      {handoffInfo && (handoffInfo.email || handoffInfo.phone || handoffInfo.url) && (
        <HandoffBanner info={handoffInfo} />
      )}

      {/* Suggestion chips */}
      <SuggestionChips
        suggestions={suggestions}
        onSelect={sendMessage}
        visible={showSuggestions && messages.length <= 1}
      />

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
