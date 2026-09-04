import { Check, Copy } from "lucide-react";
import { useState } from "react";
import SeverityBadge from "./SeverityBadge";

function DdlSuggestion({ sql }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_e) {
      /* clipboard access denied - ignore, the SQL is still visible to copy manually */
    }
  }

  return (
    <div className="ddl-suggestion">
      <div className="ddl-suggestion-header">
        <strong>Suggested DDL</strong>
        <button className="ghost-btn" onClick={copy} title="Copy to clipboard">
          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>{sql}</pre>
    </div>
  );
}

export default function FindingCard({ finding }) {
  return (
    <article className="finding-card">
      <div className="finding-header">
        <SeverityBadge severity={finding.severity} />
        <div>
          <h3>{finding.title}</h3>
          <p>
            {finding.category} · <code>{finding.node_path}</code> ·{" "}
            <span className="rule-id" title="Stable rule identifier">
              {finding.rule_id}
            </span>
          </p>
        </div>
      </div>

      <div className="columns">
        <section>
          <h4>Evidence</h4>
          <ul>
            {finding.evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4>What to check</h4>
          <ul>
            {finding.checks.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </section>
      </div>

      <div className="recommendation">
        <strong>Recommendation:</strong> {finding.recommendation}
      </div>

      {finding.ddl_suggestion && <DdlSuggestion sql={finding.ddl_suggestion} />}
    </article>
  );
}
