"use client";

import ReactMarkdown from "react-markdown";
import { useLanguage } from "../i18n/LanguageContext";

interface Source {
  url: string;
  title: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  id?: number;
  confidence?: number;
  lowConfidence?: boolean;
  feedbackGiven?: 1 | -1 | null;
}

interface Props {
  message: Message;
  onFeedback?: (messageId: number, rating: 1 | -1) => void;
}

export default function MessageBubble({ message, onFeedback }: Props) {
  const { t } = useLanguage();
  const isUser = message.role === "user";

  if (!message.content && !isUser) return null;

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      role="article"
      aria-label={isUser ? "Your message" : "Assistant message"}
    >
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-gray-100 text-gray-800 rounded-bl-md"
        }`}
      >
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <div className="text-sm markdown-content">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Low confidence warning */}
        {!isUser && message.lowConfidence && (
          <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs text-amber-700">{t("lowConfidence")}</p>
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-gray-200">
            <p className="text-xs text-gray-500 mb-1">{t("sources")}</p>
            <div className="space-y-1">
              {message.sources.map((source, i) => (
                <a
                  key={i}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-blue-600 hover:text-blue-800 truncate"
                  aria-label={`Source: ${source.title}`}
                >
                  {source.title}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Feedback buttons */}
        {!isUser && message.id && onFeedback && (
          <div className="mt-2 pt-2 border-t border-gray-200/50 flex items-center gap-2">
            {message.feedbackGiven ? (
              <span className="text-xs text-gray-400">{t("feedbackThanks")}</span>
            ) : (
              <>
                <button
                  onClick={() => onFeedback(message.id!, 1)}
                  className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-green-600 transition-colors px-1.5 py-0.5 rounded hover:bg-green-50"
                  aria-label={t("helpful")}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                  </svg>
                  {t("helpful")}
                </button>
                <button
                  onClick={() => onFeedback(message.id!, -1)}
                  className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600 transition-colors px-1.5 py-0.5 rounded hover:bg-red-50"
                  aria-label={t("notHelpful")}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                  </svg>
                  {t("notHelpful")}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
