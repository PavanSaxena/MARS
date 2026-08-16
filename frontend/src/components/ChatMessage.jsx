import DepartmentGrid from "./DepartmentGrid.jsx";
import DecisionPanel from "./DecisionPanel.jsx";
import ExplainabilityAccordion from "./ExplainabilityAccordion.jsx";

export default function ChatMessage({ message }) {
  if (message.role === "user") {
    return (
      <div className="message-row user-row">
        <div className="user-bubble">{message.text}</div>
      </div>
    );
  }

  return (
    <div className="message-row assistant-row">
      <div className="avatar" aria-hidden="true">M</div>
      <div className="assistant-content">
        {message.status === "thinking" && (
          <>
            <div className="typing-dots" aria-label="Thinking">
              <span />
              <span />
              <span />
            </div>
            <DepartmentGrid status="thinking" result={null} />
          </>
        )}

        {message.status === "error" && <div className="error-banner">{message.error}</div>}

        {message.status === "done" && message.result && (
          <>
            <DepartmentGrid status="done" result={message.result} />
            <DecisionPanel result={message.result} />
            <ExplainabilityAccordion explainability={message.result.explainability} />
          </>
        )}
      </div>
    </div>
  );
}
