"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import ChatWidget from "../components/ChatWidget";
import { useLanguage } from "../i18n/LanguageContext";

function EmbedContent() {
  const searchParams = useSearchParams();
  const { setLang } = useLanguage();

  useEffect(() => {
    const lang = searchParams.get("lang");
    if (lang === "en" || lang === "fr") {
      setLang(lang);
    }
  }, [searchParams, setLang]);

  return (
    <main className="h-screen w-screen overflow-hidden">
      <ChatWidget />
    </main>
  );
}

export default function EmbedPage() {
  return (
    <Suspense>
      <EmbedContent />
    </Suspense>
  );
}
