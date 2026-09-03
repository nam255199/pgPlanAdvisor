import { formatDeltaMs, formatMs, formatPct } from "../lib/format";
import FindingCard from "./FindingCard";

const VERDICT_LABEL = {
  regressed: "Regressed",
  improved: "Improved",
  unchanged: "Unchanged",
};

function DeltaCell({ value, formatter }) {
  if (value === null || value === undefined) return <td>-</td>;
  const cls = value > 0 ? "delta-worse" : value < 0 ? "delta-better" : "";
  return <td className={cls}>{formatter(value)}</td>;
}

export default function PlanDiff({ comparison }) {
  const { baseline, current, runtime_delta_ms, runtime_delta_pct, verdict, node_deltas, findings_added, findings_resolved } =
    comparison;

  return (
    <>
      <div className={`panel summary verdict-${verdict}`}>
        <h1>
          Comparison: <span className={`verdict-pill verdict-${verdict}`}>{VERDICT_LABEL[verdict] || verdict}</span>
        </h1>
        <p>
          Baseline: {formatMs(baseline.total_runtime_ms)} → Current: {formatMs(current.total_runtime_ms)} ·{" "}
          <strong>{formatDeltaMs(runtime_delta_ms)}</strong>
          {runtime_delta_pct !== null && runtime_delta_pct !== undefined && <> ({formatPct(runtime_delta_pct)})</>}
        </p>
      </div>

      <div className="panel">
        <h2>Node-by-node changes</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Node</th>
                <th>Table</th>
                <th>Status</th>
                <th>Baseline time</th>
                <th>Current time</th>
                <th>Δ time</th>
                <th>Δ rows</th>
              </tr>
            </thead>
            <tbody>
              {node_deltas.map((d) => (
                <tr key={d.path}>
                  <td>
                    <strong>{d.node_type}</strong>
                  </td>
                  <td>{d.relation || "-"}</td>
                  <td>
                    <span className={`status-pill status-${d.status}`}>{d.status}</span>
                  </td>
                  <td>{d.baseline_time_ms != null ? formatMs(d.baseline_time_ms) : "-"}</td>
                  <td>{d.current_time_ms != null ? formatMs(d.current_time_ms) : "-"}</td>
                  <DeltaCell value={d.time_delta_ms} formatter={formatDeltaMs} />
                  <DeltaCell value={d.rows_delta_pct} formatter={formatPct} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {findings_added.length > 0 && (
        <div className="panel">
          <h2>New findings in current</h2>
          {findings_added.map((f, i) => (
            <FindingCard finding={f} key={i} />
          ))}
        </div>
      )}

      {findings_resolved.length > 0 && (
        <div className="panel">
          <h2>Findings resolved since baseline</h2>
          {findings_resolved.map((f, i) => (
            <FindingCard finding={f} key={i} />
          ))}
        </div>
      )}

      {findings_added.length === 0 && findings_resolved.length === 0 && (
        <p className="hint">No findings appeared or disappeared between the two runs.</p>
      )}
    </>
  );
}
