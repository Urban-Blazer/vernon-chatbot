"use client";

import { useLanguage } from "../i18n/LanguageContext";

export default function LanguageToggle() {
  const { lang, setLang } = useLanguage();

  return (
    <div className="flex items-center gap-1 text-xs" role="radiogroup" aria-label="Language">
      <button
        onClick={() => setLang("en")}
        className={`px-2 py-0.5 rounded transition-colors ${
          lang === "en"
            ? "bg-white/20 text-white font-semibold"
            : "text-white/70 hover:text-white"
        }`}
        role="radio"
        aria-checked={lang === "en"}
        aria-label="English"
      >
        EN
      </button>
      <span className="text-white/40">|</span>
      <button
        onClick={() => setLang("fr")}
        className={`px-2 py-0.5 rounded transition-colors ${
          lang === "fr"
            ? "bg-white/20 text-white font-semibold"
            : "text-white/70 hover:text-white"
        }`}
        role="radio"
        aria-checked={lang === "fr"}
        aria-label="Français"
      >
        FR
      </button>
    </div>
  );
}
