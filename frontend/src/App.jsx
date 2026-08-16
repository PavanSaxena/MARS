import { useEffect, useRef, useState } from "react";
import { listModels, submitQuery, ApiError } from "./api.js";
import { loadChats, saveChats } from "./chatStore.js";
import ChatMessage from "./components/ChatMessage.jsx";
import Composer from "./components/Composer.jsx";
import Sidebar from "./components/Sidebar.jsx";

// Internal conversation identifier for the backend's memory feature.
// Intentionally never rendered — the user only ever sees the chat's title.
function newThreadId() {
  return `web-${Math.random().toString(36).slice(2, 8)}`;
}

function titleFromText(text) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > 48 ? `${flat.slice(0, 48).trim()}…` : flat;
}

const SUGGESTIONS = [
  "Should we invest in an AI-driven supply chain optimization initiative this quarter?",
  "Is it the right time to expand into the European market?",
  "Should we build our next product feature in-house or outsource it?",
  "Evaluate whether we should switch cloud providers this fiscal year.",
];

export default function App() {
  const [chats, setChats] = useState(() => loadChats());
  const [activeChatId, setActiveChatId] = useState(() => {
    const initial = loadChats();
    if (initial.length === 0) return null;
    return [...initial].sort((a, b) => b.updatedAt - a.updatedAt)[0].id;
  });
  const [models, setModels] = useState(null); // { models, default, unavailable }
  const [selectedModel, setSelectedModel] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef(null);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;
  const messages = activeChat ? activeChat.messages : [];
  const isThinking = messages.some((m) => m.role === "assistant" && m.status === "thinking");
  const sortedChats = [...chats].sort((a, b) => b.updatedAt - a.updatedAt);

  useEffect(() => {
    listModels()
      .then((data) => {
        setModels(data);
        setSelectedModel(data.default);
      })
      .catch(() => {
        // Model list is a nice-to-have (falls back to backend default if
        // omitted from the request) — don't block the UI on it.
      });
  }, []);

  // Persist on every change so a refresh (or crash) never loses history.
  useEffect(() => {
    saveChats(chats);
  }, [chats]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function startNewChat() {
    // Don't create a chat record until the first message is actually
    // sent — otherwise every click on "New chat" litters the sidebar
    // with empty conversations.
    setActiveChatId(null);
    setSidebarOpen(false);
  }

  function selectChat(id) {
    setActiveChatId(id);
    setSidebarOpen(false);
  }

  function deleteChat(id) {
    setChats((prev) => prev.filter((c) => c.id !== id));
    setActiveChatId((prev) => (prev === id ? null : prev));
  }

  function upsertAssistantMessage(chatId, messageId, patch) {
    setChats((prev) =>
      prev.map((c) =>
        c.id !== chatId
          ? c
          : {
              ...c,
              updatedAt: Date.now(),
              messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
            }
      )
    );
  }

  async function handleSend(text) {
    const trimmed = text.trim();
    if (!trimmed || isThinking) return;

    const userMsg = { id: crypto.randomUUID(), role: "user", text: trimmed };
    const assistantMsg = { id: crypto.randomUUID(), role: "assistant", status: "thinking" };

    let chatId = activeChatId;
    let threadId;

    if (chatId) {
      threadId = activeChat.threadId;
      setChats((prev) =>
        prev.map((c) =>
          c.id === chatId
            ? { ...c, messages: [...c.messages, userMsg, assistantMsg], updatedAt: Date.now() }
            : c
        )
      );
    } else {
      chatId = crypto.randomUUID();
      threadId = newThreadId();
      const newChat = {
        id: chatId,
        threadId,
        title: titleFromText(trimmed),
        messages: [userMsg, assistantMsg],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setChats((prev) => [...prev, newChat]);
      setActiveChatId(chatId);
    }

    try {
      const data = await submitQuery({
        query: trimmed,
        threadId,
        model: selectedModel || undefined,
      });
      upsertAssistantMessage(chatId, assistantMsg.id, { status: "done", result: data });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      upsertAssistantMessage(chatId, assistantMsg.id, { status: "error", error: message });
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={startNewChat}
        chats={sortedChats}
        activeChatId={activeChatId}
        onSelectChat={selectChat}
        onDeleteChat={deleteChat}
        models={models}
        selectedModel={selectedModel}
        onSelectModel={setSelectedModel}
      />

      <div className="main">
        <header className="mobile-header">
          <button
            className="icon-btn"
            aria-label="Open menu"
            onClick={() => setSidebarOpen(true)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <span className="mobile-title">MARS</span>
          <button className="icon-btn" aria-label="New chat" onClick={startNewChat}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="empty-state">
              <h1 className="empty-title">What should we decide today?</h1>
              <p className="empty-subtitle">
                Ask a business question and Finance, R&amp;D, Legal, and Operations will weigh in
                together.
              </p>
              <div className="suggestion-grid">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion-card" onClick={() => handleSend(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}
            </div>
          )}
        </div>

        <Composer onSend={handleSend} disabled={isThinking} />
      </div>
    </div>
  );
}
