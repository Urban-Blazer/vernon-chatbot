"use client";

import { useLanguage } from "../i18n/LanguageContext";

interface HandoffInfo {
  email: string;
  phone: string;
  url: string;
  summary?: string;
}

export default function HandoffBanner({ info }: { info: HandoffInfo }) {
  const { t } = useLanguage();

  const copySummary = () => {
    if (info.summary) {
      navigator.clipboard.writeText(info.summary);
    }
  };

  return (
    <div className="mx-4 my-2 p-4 bg-amber-50 border border-amber-200 rounded-xl" role="alert">
      <p className="text-sm font-medium text-amber-800 mb-3">
        {t("handoffTitle")}
      </p>

      {info.summary && (
        <div className="mb-3 p-2.5 bg-white/70 border border-amber-200 rounded-lg">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-500">{t("conversationSummary")}</span>
            <button
              onClick={copySummary}
              className="text-xs text-amber-700 hover:text-amber-900 underline transition-colors"
              aria-label={t("copySummary")}
            >
              {t("copySummary")}
            </button>
          </div>
          <p className="text-xs text-gray-700 leading-relaxed">{info.summary}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {info.email && (
          <a
            href={`mailto:${info.email}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-amber-300 text-amber-800 rounded-lg hover:bg-amber-100 transition-colors"
            aria-label={t("handoffEmail")}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            {t("handoffEmail")}
          </a>
        )}
        {info.phone && (
          <a
            href={`tel:${info.phone}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-amber-300 text-amber-800 rounded-lg hover:bg-amber-100 transition-colors"
            aria-label={t("handoffPhone")}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            {t("handoffPhone")}
          </a>
        )}
        {info.url && (
          <a
            href={info.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-amber-300 text-amber-800 rounded-lg hover:bg-amber-100 transition-colors"
            aria-label={t("handoffVisit")}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            {t("handoffVisit")}
          </a>
        )}
      </div>
    </div>
  );
}
