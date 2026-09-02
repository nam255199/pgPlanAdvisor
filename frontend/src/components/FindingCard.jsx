import SeverityBadge from "./SeverityBadge";

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
    </article>
  );
}
