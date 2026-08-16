// Persists chats (message history + each chat's own backend thread id) to
// localStorage so a refresh doesn't wipe the conversation, and so the
// sidebar has something to list and switch between.
const STORAGE_KEY = "mars.chats.v1";

function sanitize(chats) {
  // A page refresh mid-request leaves an assistant message stuck in
  // "thinking" forever (nothing will ever resolve it) — surface those as
  // an interrupted response instead of a spinner that never stops.
  return chats.map((chat) => ({
    ...chat,
    messages: chat.messages.map((m) =>
      m.role === "assistant" && m.status === "thinking"
        ? {
            ...m,
            status: "error",
            error: "This response was interrupted. Try sending your question again.",
          }
        : m
    ),
  }));
}

export function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? sanitize(parsed) : [];
  } catch {
    return [];
  }
}

export function saveChats(chats) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
  } catch {
    // Storage full, disabled, or unavailable (e.g. private browsing) —
    // chats just won't persist across a refresh; nothing else to do.
  }
}
