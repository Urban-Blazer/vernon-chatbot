"use client";

import ChatWidget from "./components/ChatWidget";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Customer Support
          </h1>
          <p className="text-gray-600">
            Ask me anything — I&apos;ll find the answer from our website.
          </p>
        </div>
        <ChatWidget />
      </div>
    </main>
  );
}
