import { riskBadgeClass } from "../departments.js";
import Markdown from "./Markdown.jsx";

export default function DecisionPanel({ result }) {
  const { key_insights, conflicts, final_decision } = result;

  return (
    <div className="panel decision-panel">
      <div className="decision-head">
        <h2 className="decision-title">Final decision</h2>
        <div className="badges">
          {final_decision.risk_level && (
            <span className={riskBadgeClass(final_decision.risk_level)}>
              risk: {final_decision.risk_level}
            </span>
          )}
          {final_decision.roi && <span className="badge">roi: {final_decision.roi}</span>}
        </div>
      </div>

      <div className="decision-text">
        <Markdown>{final_decision.decision}</Markdown>
      </div>

      {final_decision.notes && (
        <div className="decision-notes">
          <strong>Notes — </strong>
          <Markdown inline>{final_decision.notes}</Markdown>
        </div>
      )}

      <div className="grid-2">
        <div>
          <p className="panel-title">Key insights</p>
          {key_insights.length > 0 ? (
            <ul className="insight-list">
              {key_insights.map((point, i) => (
                <li key={i}>
                  <Markdown inline>{point}</Markdown>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">None reported.</p>
          )}
        </div>

        <div>
          <p className="panel-title">Conflicts</p>
          {conflicts.length > 0 ? (
            <ul className="conflict-list">
              {conflicts.map((point, i) => (
                <li key={i}>
                  <Markdown inline>{point}</Markdown>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">None detected.</p>
          )}
        </div>
      </div>
    </div>
  );
}
