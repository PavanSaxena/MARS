import { useState } from "react";
import { DEPARTMENTS, parseExplainability } from "../departments.js";
import Markdown from "./Markdown.jsx";

export default function ExplainabilityAccordion({ explainability }) {
  const blocks = parseExplainability(explainability);
  const [openKey, setOpenKey] = useState(null);

  const entries = DEPARTMENTS.filter((dept) => blocks[dept.key]);
  if (entries.length === 0) return null;

  return (
    <div className="panel explainability">
      <p className="panel-title">Explainability</p>
      {entries.map((dept) => {
        const isOpen = openKey === dept.key;
        return (
          <div key={dept.key} className="accordion-item">
            <button
              className="accordion-trigger"
              aria-expanded={isOpen}
              onClick={() => setOpenKey(isOpen ? null : dept.key)}
            >
              <span className="dot" style={{ "--dept-color": dept.color }} />
              <span className="label">{dept.label}</span>
              <span className="chevron">▶</span>
            </button>
            {isOpen && (
              <div className="accordion-panel">
                <Markdown>{blocks[dept.key]}</Markdown>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
