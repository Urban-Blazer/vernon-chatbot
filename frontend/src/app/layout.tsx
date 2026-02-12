"use client";

import "./globals.css";
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";

function HtmlWrapper({ children }: { children: React.ReactNode }) {
  const { lang, t } = useLanguage();

  return (
    <html lang={lang}>
      <head>
        <title>
          {lang === "fr"
            ? "Vernon Chatbot — Service à la clientèle"
            : "Vernon Chatbot — Customer Support"}
        </title>
        <meta
          name="description"
          content="AI-powered customer service chatbot for the City of Vernon"
        />
      </head>
      <body className="bg-gray-50 min-h-screen">
        <a
          href="#chat-main"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50
                     focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg
                     focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          {t("skipToContent")}
        </a>
        {children}
      </body>
    </html>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <LanguageProvider>
      <HtmlWrapper>{children}</HtmlWrapper>
    </LanguageProvider>
  );
}
