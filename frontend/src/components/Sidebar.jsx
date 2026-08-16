export default function Sidebar({
  open,
  onClose,
  onNewChat,
  chats,
  activeChatId,
  onSelectChat,
  onDeleteChat,
  models,
  selectedModel,
  onSelectModel,
}) {
  return (
    <>
      {open && <div className="sidebar-scrim" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark">M</span>
            <span className="brand-name">MARS</span>
          </div>
          <button className="icon-btn sidebar-close" aria-label="Close menu" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <button className="new-chat-btn" onClick={onNewChat}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          New chat
        </button>

        <nav className="chat-list">
          {chats.length === 0 ? (
            <p className="chat-list-empty">No chats yet</p>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.id}
                className={`chat-item ${chat.id === activeChatId ? "chat-item-active" : ""}`}
                onClick={() => onSelectChat(chat.id)}
              >
                <span className="chat-item-title">{chat.title || "New chat"}</span>
                <button
                  className="chat-item-delete"
                  aria-label="Delete chat"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteChat(chat.id);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </nav>

        {models && (
          <div className="sidebar-model">
            <label htmlFor="model-select">Model</label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => onSelectModel(e.target.value)}
            >
              {models.models.map((m) => (
                <option key={m} value={m} disabled={models.unavailable.includes(m)}>
                  {m}
                  {models.unavailable.includes(m) ? " (no key)" : ""}
                </option>
              ))}
            </select>
          </div>
        )}
      </aside>
    </>
  );
}
