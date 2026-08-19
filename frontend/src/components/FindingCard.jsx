import React from "react";

export default function FindingCard({ finding }) {
  const cls = `severity ${finding.severity}`;
  return (
    <article className="finding-card">
      <div className="finding-header">
        <span className={cls}>{finding.severity}</span>
        <div>
          <h3>{finding.title}</h3>
          <p>{finding.category} · {finding.node_path}</p>
        </div>
      </div>

      <div className="columns">
        <section>
          <h4>Evidence</h4>
          <ul>{finding.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </section>
        <section>
          <h4>What to check</h4>
          <ul>{finding.checks.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </section>
      </div>

      <div className="recommendation">
        <strong>Recommendation:</strong> {finding.recommendation}
      </div>
    </article>
  );
}
