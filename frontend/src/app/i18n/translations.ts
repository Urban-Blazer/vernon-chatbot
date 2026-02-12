export const translations = {
  en: {
    title: "Customer Support",
    subtitle: "Ask me anything — I'll find the answer from our website.",
    placeholder: "Type your question...",
    send: "Send",
    poweredBy: "Powered by AI — responses are based on our website content",
    privacyNotice:
      "Conversations are stored for 90 days to improve service. No personal information is retained.",
    talkToPerson: "Talk to a person",
    sources: "Sources:",
    greeting:
      "Hi! I'm your customer support assistant for the City of Vernon. How can I help you today?",
    thinking: "Thinking...",
    handoffTitle: "Would you like to talk to a real person?",
    handoffEmail: "Email Us",
    handoffPhone: "Call Us",
    handoffVisit: "Visit Contact Page",
    lowConfidence:
      "I'm not fully confident in this answer. You may want to verify on vernon.ca or talk to a person.",
    helpful: "Helpful",
    notHelpful: "Not helpful",
    feedbackThanks: "Thank you for your feedback!",
    errorFiltered:
      "Your message was filtered for safety. Please rephrase your question.",
    errorGeneric: "Something went wrong. Please try again.",
    skipToContent: "Skip to main content",
    conversationSummary: "Conversation summary:",
    copySummary: "Copy summary",
  },
  fr: {
    title: "Service à la clientèle",
    subtitle:
      "Posez-moi une question — je trouverai la réponse sur notre site Web.",
    placeholder: "Tapez votre question...",
    send: "Envoyer",
    poweredBy:
      "Propulsé par l'IA — les réponses sont basées sur le contenu de notre site Web",
    privacyNotice:
      "Les conversations sont conservées pendant 90 jours pour améliorer le service. Aucune information personnelle n'est conservée.",
    talkToPerson: "Parler à une personne",
    sources: "Sources :",
    greeting:
      "Bonjour ! Je suis votre assistant du service à la clientèle de la Ville de Vernon. Comment puis-je vous aider ?",
    thinking: "Réflexion...",
    handoffTitle: "Souhaitez-vous parler à une vraie personne ?",
    handoffEmail: "Nous envoyer un courriel",
    handoffPhone: "Nous appeler",
    handoffVisit: "Visiter la page de contact",
    lowConfidence:
      "Je ne suis pas totalement certain de cette réponse. Vous pouvez vérifier sur vernon.ca ou parler à une personne.",
    helpful: "Utile",
    notHelpful: "Pas utile",
    feedbackThanks: "Merci pour vos commentaires !",
    errorFiltered:
      "Votre message a été filtré pour des raisons de sécurité. Veuillez reformuler votre question.",
    errorGeneric: "Quelque chose s'est mal passé. Veuillez réessayer.",
    skipToContent: "Passer au contenu principal",
    conversationSummary: "Resume de la conversation :",
    copySummary: "Copier le resume",
  },
} as const;

export type Language = "en" | "fr";
export type TranslationKey = keyof (typeof translations)["en"];
